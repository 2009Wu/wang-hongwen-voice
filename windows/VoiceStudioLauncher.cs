// SPDX-License-Identifier: GPL-3.0-only
// Build using the .NET Framework C# compiler; no third-party GUI runtime required.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class Program {
    [STAThread]
    private static int Main(string[] args) {
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
        if (args.Length > 0 && args[0] == "--echo-arguments") {
            Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
            Console.WriteLine(new JavaScriptSerializer().Serialize(args.Skip(1).ToArray())); return 0;
        }
        string root = AppDomain.CurrentDomain.BaseDirectory;
        for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--root") root = args[++i];
        root = Path.GetFullPath(root);
        if (args.Contains("--self-test")) return Engine.SelfTest(root);
        if (args.Contains("--install-only") || args.Contains("--serve-only") || args.Contains("--diagnose")) {
            try {
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
                var engine = new Engine(root, (n, message) => Console.WriteLine(n + "% " + message), Console.WriteLine);
                if (args.Contains("--diagnose")) { Console.WriteLine(engine.HardwareCheck(false)); return 0; }
                if (args.Contains("--install-only")) { engine.Setup(CancellationToken.None); return 0; }
                int port = 7860;
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--port") port = int.Parse(args[++i]);
                using (Process server = engine.StartServer(port, CancellationToken.None)) { Console.WriteLine("@@READY " + engine.AppUrl); server.WaitForExit(); return server.ExitCode; }
            } catch (Exception error) { Console.Error.WriteLine(error.ToString()); return 1; }
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new LauncherForm(root));
        return 0;
    }
}

internal sealed class Engine {
    internal readonly string Root;
    internal readonly string Runtime;
    internal string AppUrl;
    private readonly Action<int, string> report;
    private readonly Action<string> log;
    private readonly object logLock = new object();
    private readonly JavaScriptSerializer json = new JavaScriptSerializer();
    private int gpuIndex;
    private volatile Process activeSetupProcess;
    private const string Revision = "windows-setup-1";
    internal Engine(string root, Action<int, string> progress, Action<string> logger) {
        Root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Runtime = Path.Combine(Root, ".runtime"); report = progress; log = logger;
    }
    internal string BasePython { get { return Path.Combine(Runtime, "python", "tools", "python.exe"); } }
    private string Python(string env) { return Path.Combine(Runtime, env, "Scripts", "python.exe"); }
    private string Tool(string name) {
        string folder = Path.Combine(Runtime, "ffmpeg");
        if (!Directory.Exists(folder)) return null;
        return Directory.EnumerateFiles(folder, name + ".exe", SearchOption.AllDirectories).FirstOrDefault();
    }
    internal string LogPath { get { return Path.Combine(Runtime, "setup.log"); } }
    private void WriteLog(string message) {
        if (String.IsNullOrEmpty(message)) return;
        Directory.CreateDirectory(Runtime);
        lock (logLock) File.AppendAllText(LogPath, DateTime.Now.ToString("HH:mm:ss ") + message + Environment.NewLine, Encoding.UTF8);
        log(message);
    }
    private void Stage(int value, string message) { report(value, message); WriteLog(message); }
    internal static string Quote(string value) {
        // Windows CommandLineToArgvW / CRT quoting, including trailing backslashes.
        var output = new StringBuilder("\""); int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { output.Append('\\', slashes * 2 + 1); output.Append(c); slashes = 0; continue; }
            output.Append('\\', slashes); slashes = 0; output.Append(c);
        }
        output.Append('\\', slashes * 2); output.Append('"'); return output.ToString();
    }
    private ProcessStartInfo ProcessInfo(string executable, IEnumerable<string> args) {
        var info = new ProcessStartInfo(executable, String.Join(" ", args.Select(Quote))) {
            WorkingDirectory = Root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        var env = info.EnvironmentVariables;
        // Process-local settings only: preserve system PATH, Python, and registry settings.
        env.Remove("PYTHONHOME"); env.Remove("PYTHONPATH");
        env["PYTHONNOUSERSITE"] = "1"; env["PYTHONIOENCODING"] = "utf-8"; env["PYTHONUNBUFFERED"] = "1";
        env["PYTHONPYCACHEPREFIX"] = Path.Combine(Runtime, "pycache");
        env["PIP_CACHE_DIR"] = Path.Combine(Runtime, "pip-cache"); env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1";
        env["HF_HOME"] = Path.Combine(Root, ".cache", "huggingface");
        env["HF_HUB_CACHE"] = Path.Combine(Root, ".cache", "huggingface", "hub");
        env["MODEL_CACHE"] = Path.Combine(Root, ".cache"); env["TORCH_HOME"] = Path.Combine(Root, ".cache", "torch");
        env["NUMBA_CACHE_DIR"] = Path.Combine(Root, ".cache", "numba"); env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1";
        env["GRADIO_ANALYTICS_ENABLED"] = "False"; env["TOKENIZERS_PARALLELISM"] = "false";
        env["VOICE_STUDIO_DESKTOP"] = "1"; env["HOST"] = "127.0.0.1";
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"; env["CUDA_VISIBLE_DEVICES"] = gpuIndex.ToString(CultureInfo.InvariantCulture);
        env["SING_PYTHON"] = Python("singing"); env["TTS_PYTHON"] = Python("speech");
        string ffmpeg = Tool("ffmpeg"), ffprobe = Tool("ffprobe");
        if (ffmpeg != null) { env["FFMPEG"] = ffmpeg; env["PATH"] = Path.GetDirectoryName(ffmpeg) + ";" + env["PATH"]; }
        if (ffprobe != null) env["FFPROBE"] = ffprobe;
        return info;
    }
    private Process Spawn(string executable, string[] args, bool server) {
        Process p = new Process { StartInfo = ProcessInfo(executable, args), EnableRaisingEvents = true };
        string serverLog = Path.Combine(Runtime, "app.log");
        DataReceivedEventHandler receive = (sender, e) => {
            if (e.Data == null) return;
            if (server) { lock (logLock) File.AppendAllText(serverLog, e.Data + Environment.NewLine, Encoding.UTF8); log(e.Data); }
            else WriteLog(e.Data);
        };
        p.OutputDataReceived += receive; p.ErrorDataReceived += receive;
        p.Start(); p.BeginOutputReadLine(); p.BeginErrorReadLine(); return p;
    }
    private void Run(string executable, string[] args, CancellationToken token, int minutes) {
        token.ThrowIfCancellationRequested();
        WriteLog("Running " + Path.GetFileName(executable) + " " + String.Join(" ", args.Select(Quote)));
        using (Process p = Spawn(executable, args, false)) {
            activeSetupProcess = p;
            var timer = Stopwatch.StartNew();
            try {
                while (!p.WaitForExit(300)) {
                    token.ThrowIfCancellationRequested();
                    if (timer.Elapsed.TotalMinutes > minutes) throw new TimeoutException("This setup step took too long. Check the internet connection and try again.");
                }
                p.WaitForExit();
                if (p.ExitCode != 0) throw new InvalidOperationException("A setup check or package install failed. Open the setup log for details, then choose Repair setup.");
            } catch { KillTree(p); throw; }
            finally { activeSetupProcess = null; }
        }
    }
    internal void CancelSetup() { KillTree(activeSetupProcess); }
    internal static void KillTree(Process p) {
        try {
            if (p == null || p.HasExited) return;
            using (var killer = Process.Start(new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "taskkill.exe"), "/PID " + p.Id + " /T /F") {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
            })) { killer.WaitForExit(15000); }
        } catch (InvalidOperationException) { } catch (System.ComponentModel.Win32Exception) { }
    }
    internal string HardwareCheck(bool disk) {
        if (!Environment.Is64BitOperatingSystem || !Environment.Is64BitProcess) throw new InvalidOperationException("Use 64-bit Windows 10 or 11 for this release.");
        if (!File.Exists(Path.Combine(Root, "app.py")) || !File.Exists(Path.Combine(Root, "windows", "runtime-pins.json")))
            throw new InvalidOperationException("Extract the complete ZIP first. Keep this launcher beside app.py and the windows folder.");
        var info = new ProcessStartInfo("nvidia-smi", "--query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits") {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };
        string output;
        try { using (Process p = Process.Start(info)) {
            output = p.StandardOutput.ReadToEnd();
            if (!p.WaitForExit(15000) || p.ExitCode != 0) throw new InvalidOperationException("NVIDIA GPU check failed. Install a current NVIDIA graphics driver and restart Windows.");
        }} catch (System.ComponentModel.Win32Exception) { throw new InvalidOperationException("An NVIDIA GPU and its graphics driver are required. This release recommends 16 GB+ GPU memory."); }
        int best = 0; string summary = "";
        foreach (string line in output.Split(new[] {'\r','\n'}, StringSplitOptions.RemoveEmptyEntries)) {
            string[] parts = line.Split(','); int index, memory;
            if (parts.Length >= 4 && int.TryParse(parts[0].Trim(), out index) && int.TryParse(parts[2].Trim(), out memory) && memory > best) {
                best = memory; gpuIndex = index; summary = parts[1].Trim() + " · " + (memory / 1024.0).ToString("0.0", CultureInfo.InvariantCulture) + " GB · driver " + parts[3].Trim();
            }
        }
        if (best < 14500) throw new InvalidOperationException("This beginner release needs a 16 GB-class NVIDIA GPU. The detected GPU has less memory.");
        if (disk) {
            var drive = new DriveInfo(Path.GetPathRoot(Root));
            if (drive.AvailableFreeSpace < 30L * 1024 * 1024 * 1024) throw new InvalidOperationException("Free at least 30 GB on the drive containing this folder before setup.");
        }
        return summary;
    }
    private static string Sha(string path) { using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant(); }
    private string Fingerprint() {
        var text = new StringBuilder(Revision + Path.GetFullPath(Root).ToUpperInvariant());
        foreach (string name in new[] {"requirements-ui.txt", "requirements-singing.txt", "requirements-tts.txt", "windows/runtime-pins.json", "windows/check_install.py"}) text.Append(Sha(Path.Combine(Root, name)));
        using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(Encoding.UTF8.GetBytes(text.ToString()))).Replace("-", "");
    }
    internal bool IsReady() {
        try {
            if (!File.Exists(Path.Combine(Runtime, "ready.json"))) return false;
            var data = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Runtime, "ready.json")));
            return (string)data["fingerprint"] == Fingerprint() && File.Exists(BasePython) && File.Exists(Python("ui")) && File.Exists(Python("singing")) && File.Exists(Python("speech")) && Tool("ffmpeg") != null && Tool("ffprobe") != null;
        } catch { return false; }
    }
    private string Download(Dictionary<string, object> pin, CancellationToken token, int progress) {
        string folder = Path.Combine(Runtime, "downloads"); Directory.CreateDirectory(folder);
        string file = Path.Combine(folder, Path.GetFileName((string)pin["file"]));
        string expected = (string)pin["sha256"];
        if (File.Exists(file) && Sha(file) == expected) return file;
        string partial = file + ".partial";
        using (var client = new HttpClient { Timeout = TimeSpan.FromHours(1) }) {
            client.DefaultRequestHeaders.UserAgent.ParseAdd("WangVoiceStudio/0.2");
            using (var response = client.GetAsync((string)pin["url"], HttpCompletionOption.ResponseHeadersRead, token).GetAwaiter().GetResult()) {
                response.EnsureSuccessStatusCode();
                long total = response.Content.Headers.ContentLength ?? 0, done = 0; var timer = Stopwatch.StartNew();
                using (var input = response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()) using (var output = File.Create(partial)) {
                    byte[] buffer = new byte[128 * 1024]; int n;
                    while ((n = input.ReadAsync(buffer, 0, buffer.Length, token).GetAwaiter().GetResult()) > 0) {
                        output.Write(buffer, 0, n); done += n;
                        if (timer.ElapsedMilliseconds > 600) { report(progress, "Downloading " + pin["file"] + " · " + (done / 1024 / 1024) + (total > 0 ? "/" + (total / 1024 / 1024) : "") + " MB"); timer.Restart(); }
                    }
                }
            }
        }
        if (Sha(partial) != expected) throw new InvalidDataException("A download did not match its verified checksum. Try setup again; the damaged download will not be used.");
        if (File.Exists(file)) File.Delete(file);
        File.Move(partial, file); return file;
    }
    internal static string SafeZipPath(string destination, string entry) {
        string prefix = Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string result = Path.GetFullPath(Path.Combine(prefix, entry));
        if (!result.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Unsafe archive path rejected.");
        return result;
    }
    private static void Extract(string archive, string destination, CancellationToken token) {
        Directory.CreateDirectory(destination);
        using (var zip = ZipFile.OpenRead(archive)) foreach (var entry in zip.Entries) {
            token.ThrowIfCancellationRequested();
            string path = SafeZipPath(destination, entry.FullName);
            if (String.IsNullOrEmpty(entry.Name)) { Directory.CreateDirectory(path); continue; }
            Directory.CreateDirectory(Path.GetDirectoryName(path)); entry.ExtractToFile(path, true);
        }
    }
    private void Pip(string python, string[] args, CancellationToken token) {
        Run(python, new[] {"-m", "pip", "install", "--no-input", "--progress-bar", "off", "--disable-pip-version-check", "--no-warn-script-location"}.Concat(args).ToArray(), token, 90);
    }
    internal void Setup(CancellationToken token) {
        Directory.CreateDirectory(Runtime);
        using (var setupLock = new FileStream(Path.Combine(Runtime, "setup.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None)) {
            Stage(2, "Checking your graphics card and free space…"); WriteLog(HardwareCheck(true));
            string readyMarker = Path.Combine(Runtime, "ready.json");
            if (File.Exists(readyMarker)) File.Delete(readyMarker);
            var pins = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Root, "windows", "runtime-pins.json")));
            if (!File.Exists(BasePython)) {
                Stage(5, "Preparing a private Python runtime…");
                string archive = Download((Dictionary<string, object>)pins["python"], token, 8);
                Extract(archive, Path.Combine(Runtime, "python"), token);
            }
            if (Tool("ffmpeg") == null || Tool("ffprobe") == null) {
                Stage(12, "Preparing the audio and video tools…");
                string archive = Download((Dictionary<string, object>)pins["ffmpeg"], token, 15);
                Extract(archive, Path.Combine(Runtime, "ffmpeg"), token);
            }
            Stage(20, "Installing the GPU runtime. This is a large download; please keep this window open.");
            Pip(BasePython, new[] {"numpy==1.26.4"}, token);
            Pip(BasePython, new[] {"torch==2.7.1", "torchaudio==2.7.1", "--index-url", "https://download.pytorch.org/whl/cu128"}, token);
            Stage(40, "Creating isolated app environments…");
            foreach (string env in new[] {"ui", "singing", "speech"}) {
                string config = Path.Combine(Runtime, env, "pyvenv.cfg");
                bool exists = File.Exists(Python(env));
                bool correctHome = File.Exists(config) && File.ReadAllText(config).IndexOf("home = " + Path.GetDirectoryName(BasePython), StringComparison.OrdinalIgnoreCase) >= 0;
                if (exists && correctHome) continue;
                var args = new List<string> {"-m", "venv"}; if (exists) args.Add("--upgrade"); if (env != "ui") args.Add("--system-site-packages"); args.Add(Path.Combine(Runtime, env));
                Run(BasePython, args.ToArray(), token, 10);
            }
            Stage(48, "Installing the interface…"); Pip(Python("ui"), new[] {"-r", Path.Combine(Root, "requirements-ui.txt")}, token);
            Stage(62, "Installing the singing tools…"); Pip(Python("singing"), new[] {"-r", Path.Combine(Root, "requirements-singing.txt")}, token);
            Stage(78, "Installing the speech tools…"); Pip(Python("speech"), new[] {"-r", Path.Combine(Root, "requirements-tts.txt")}, token);
            Stage(90, "Checking the GPU and installed components…");
            string doctor = Path.Combine(Root, "windows", "check_install.py");
            Run(BasePython, new[] {doctor, "gpu"}, token, 5);
            Run(BasePython, new[] {doctor, "tools"}, token, 2);
            Run(Python("ui"), new[] {doctor, "ui"}, token, 5);
            Run(Python("singing"), new[] {doctor, "singing"}, token, 5);
            Run(Python("speech"), new[] {doctor, "speech"}, token, 5);
            File.WriteAllText(Path.Combine(Runtime, "ready.json"), json.Serialize(new { fingerprint = Fingerprint(), created_utc = DateTime.UtcNow.ToString("o"), version = "0.2.0" }));
            Stage(100, "Setup complete. You can open Voice Studio.");
        }
    }
    private static int FindPort(int start) {
        for (int port = start; port < start + 100; port++) {
            var listener = new TcpListener(IPAddress.Loopback, port);
            try { listener.Start(); return port; } catch (SocketException) { } finally { listener.Stop(); }
        }
        throw new InvalidOperationException("No free local app port was found. Close other copies of the app and try again.");
    }
    internal Process StartServer(int startPort, CancellationToken token) {
        if (!IsReady()) throw new InvalidOperationException("Setup has not completed. Choose Set up Voice Studio or Repair setup first.");
        Stage(100, "Checking the graphics card…"); WriteLog(HardwareCheck(false));
        Run(BasePython, new[] {Path.Combine(Root, "windows", "check_install.py"), "gpu"}, token, 5);
        int port = FindPort(startPort);
        var info = ProcessInfo(Python("ui"), new[] {Path.Combine(Root, "app.py")});
        info.EnvironmentVariables["PORT"] = port.ToString(CultureInfo.InvariantCulture);
        Process server = new Process { StartInfo = info, EnableRaisingEvents = true };
        string appLog = Path.Combine(Runtime, "app.log");
        DataReceivedEventHandler receive = (sender, e) => { if (e.Data != null) { lock (logLock) File.AppendAllText(appLog, e.Data + Environment.NewLine, Encoding.UTF8); log(e.Data); } };
        server.OutputDataReceived += receive; server.ErrorDataReceived += receive;
        server.Start(); server.BeginOutputReadLine(); server.BeginErrorReadLine();
        AppUrl = "http://127.0.0.1:" + port;
        Stage(100, "Opening the local interface…");
        using (var client = new HttpClient(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(2) }) {
            var timer = Stopwatch.StartNew();
            try {
                while (timer.Elapsed.TotalMinutes < 3) {
                    token.ThrowIfCancellationRequested();
                    if (server.HasExited) throw new InvalidOperationException("The interface did not start. Open app.log for details or choose Repair setup.");
                    try { if (client.GetAsync(AppUrl, token).GetAwaiter().GetResult().IsSuccessStatusCode) { Stage(100, "Voice Studio is ready. Keep this launcher open while using the app."); return server; } }
                    catch (HttpRequestException) { } catch (TaskCanceledException) { token.ThrowIfCancellationRequested(); }
                    Thread.Sleep(350);
                }
                throw new TimeoutException("The interface took too long to open. Check app.log and try Repair setup.");
            } catch { KillTree(server); server.Dispose(); throw; }
        }
    }
    internal static int SelfTest(string root) {
        if (Quote("a b") != "\"a b\"" || Quote("a\"b") != "\"a\\\"b\"" || Quote("a\\") != "\"a\\\\\"") return 1;
        string destination = Path.Combine(root, "work", "zip-guard-test");
        if (!SafeZipPath(destination, "a/b.txt").EndsWith(Path.Combine("a", "b.txt"))) return 2;
        foreach (string evil in new[] {"../outside.txt", "../../outside.txt", Path.Combine(Path.GetPathRoot(root), "outside.txt")}) {
            bool rejected = false; try { SafeZipPath(destination, evil); } catch (InvalidDataException) { rejected = true; }
            if (!rejected) return 3;
        }
        string[] samples = new[] {"a b", "a\"b", "C:\\folder with spaces\\", "中文路径", "a & b | $(x)", ""};
        string executable = System.Reflection.Assembly.GetExecutingAssembly().Location;
        using (var p = Process.Start(new ProcessStartInfo(executable, String.Join(" ", new[] {"--echo-arguments"}.Concat(samples).Select(Quote))) {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, StandardOutputEncoding = Encoding.UTF8
        })) {
            string output = p.StandardOutput.ReadToEnd(); p.WaitForExit();
            string[] actual = new JavaScriptSerializer().Deserialize<string[]>(output);
            if (p.ExitCode != 0 || !actual.SequenceEqual(samples)) return 4;
        }
        Console.WriteLine("Windows argument round-trip and archive-boundary checks passed."); return 0;
    }
}

internal sealed class LauncherForm : Form {
    private readonly Engine engine;
    private readonly Label status = new Label();
    private readonly Label hardware = new Label();
    private readonly ProgressBar progress = new ProgressBar();
    private readonly TextBox detail = new TextBox();
    private readonly CheckBox showDetail = new CheckBox();
    private readonly Label quickHelp = new Label();
    private readonly Button primary = new Button();
    private readonly Button repair = new Button();
    private readonly Button stop = new Button();
    private CancellationTokenSource cancel;
    private Process server;
    private bool busy;
    internal LauncherForm(string root) {
        Text = "Wang Hongwen Voice Studio"; Size = new Size(820, 630); MinimumSize = new Size(760, 580); StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(248, 246, 242); Font = new Font("Segoe UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
        var title = new Label { Text = "Voice Studio", Font = new Font("Segoe UI", 26, FontStyle.Bold), ForeColor = Color.FromArgb(36, 43, 43), Location = new Point(30, 22), Size = new Size(700, 54) };
        var subtitle = new Label { UseMnemonic = false, Text = "Wang Hongwen · AI singing covers & text to speech", Location = new Point(34, 80), Size = new Size(700, 27), ForeColor = Color.FromArgb(115, 62, 50) };
        hardware.SetBounds(34, 121, 730, 42); hardware.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right; hardware.ForeColor = Color.FromArgb(90, 100, 95); hardware.Text = "Windows 10/11 · NVIDIA GPU with 16 GB+ memory · 30 GB free space";
        status.SetBounds(34, 175, 730, 52); status.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right; status.Font = new Font("Segoe UI", 12, FontStyle.Bold);
        progress.SetBounds(34, 233, 730, 15); progress.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        var hint = new Label { Text = "First setup downloads several GB. AI models download on first generation.\nEverything is kept in this app folder; your system Python is not changed.", Location = new Point(34, 263), Size = new Size(730, 52), ForeColor = Color.FromArgb(103, 112, 109), Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right };
        primary.SetBounds(34, 329, 300, 44); primary.UseMnemonic = false; primary.BackColor = Color.FromArgb(158, 57, 46); primary.ForeColor = Color.White; primary.FlatStyle = FlatStyle.Flat;
        repair.SetBounds(350, 329, 180, 44); repair.Text = "Repair setup"; repair.FlatStyle = FlatStyle.Flat;
        stop.SetBounds(546, 329, 150, 44); stop.Text = "Stop"; stop.FlatStyle = FlatStyle.Flat; stop.Enabled = false;
        showDetail.SetBounds(34, 389, 300, 25); showDetail.Text = "Show setup details";
        quickHelp.SetBounds(34, 428, 730, 100); quickHelp.Text = "When the browser opens, choose Sing a song or Text to speech.\nUpload your song or enter your text, then click Generate.\nSave the finished audio using the download buttons."; quickHelp.ForeColor = Color.FromArgb(103, 112, 109);
        detail.SetBounds(34, 425, 730, 104); detail.Multiline = true; detail.ScrollBars = ScrollBars.Vertical; detail.ReadOnly = true; detail.BackColor = Color.White; detail.Font = new Font("Consolas", 8); detail.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right; detail.Visible = false;
        showDetail.CheckedChanged += (sender, e) => { detail.Visible = showDetail.Checked; quickHelp.Visible = !showDetail.Checked; };
        var logs = new LinkLabel { Text = "Open setup log", Location = new Point(34, 545), Size = new Size(190, 24), Anchor = AnchorStyles.Bottom | AnchorStyles.Left };
        logs.LinkClicked += (sender, e) => { if (File.Exists(engine.LogPath)) Process.Start(new ProcessStartInfo(engine.LogPath) { UseShellExecute = true }); };
        Controls.AddRange(new Control[] {title, subtitle, hardware, status, progress, hint, primary, repair, stop, showDetail, quickHelp, detail, logs});
        engine = new Engine(root, UpdateProgress, AppendLog);
        RefreshButtons();
        primary.Click += async (sender, e) => { if (server != null && !server.HasExited) OpenApp(); else await BeginWork(!engine.IsReady()); };
        repair.Click += async (sender, e) => await BeginWork(true);
        stop.Click += (sender, e) => { if (cancel != null) cancel.Cancel(); engine.CancelSetup(); Engine.KillTree(server); server = null; RefreshButtons(); };
        FormClosing += (sender, e) => {
            if (busy && MessageBox.Show("Setup is still running. Stop it and close? You can resume setup later.", Text, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) { e.Cancel = true; return; }
            if (cancel != null) cancel.Cancel(); engine.CancelSetup(); Engine.KillTree(server);
        };
        Shown += async (sender, e) => { try { string text = await Task.Run(() => engine.HardwareCheck(false)); hardware.Text = text; } catch (Exception error) { hardware.Text = error.Message; } };
    }
    private void RefreshButtons() {
        if (busy) { primary.Enabled = false; repair.Enabled = false; stop.Enabled = true; return; }
        bool running = server != null && !server.HasExited;
        primary.Enabled = true; primary.Text = running ? "Open the app in my browser" : engine.IsReady() ? "Open Voice Studio" : "Set up & open Voice Studio";
        repair.Enabled = !running; stop.Enabled = running;
        if (!running) status.Text = engine.IsReady() ? "Ready to open." : "Welcome. Set up the app once to get started.";
    }
    private void UpdateProgress(int value, string text) {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { try { BeginInvoke(new Action<int, string>(UpdateProgress), value, text); } catch (InvalidOperationException) { } return; }
        progress.Value = Math.Max(0, Math.Min(100, value)); status.Text = text;
    }
    private void AppendLog(string text) {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { try { BeginInvoke(new Action<string>(AppendLog), text); } catch (InvalidOperationException) { } return; }
        if (detail.TextLength > 60000) detail.Text = detail.Text.Substring(detail.TextLength - 30000);
        detail.AppendText(text + Environment.NewLine);
    }
    private void OpenApp() { if (!String.IsNullOrEmpty(engine.AppUrl)) Process.Start(new ProcessStartInfo(engine.AppUrl) { UseShellExecute = true }); }
    private async Task BeginWork(bool setup) {
        busy = true; RefreshButtons(); cancel = new CancellationTokenSource(); string errorMessage = null;
        try {
            await Task.Run(() => { if (setup) engine.Setup(cancel.Token); server = engine.StartServer(7860, cancel.Token); });
            OpenApp();
        } catch (OperationCanceledException) { errorMessage = "Stopped. You can resume by starting setup again."; }
        catch (Exception error) { errorMessage = error.Message; AppendLog(error.ToString()); }
        finally { busy = false; RefreshButtons(); if (errorMessage != null) { status.Text = errorMessage; showDetail.Checked = true; } }
    }
}
