// SPDX-License-Identifier: GPL-3.0-only
// Build using the .NET Framework C# compiler and Microsoft WebView2 SDK.
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
        if (args.Contains("--self-test")) { int result = DesktopIntegration.SelfTest(root); return result == 0 ? Engine.SelfTest(root) : result; }
        if (args.Contains("--create-shortcut")) {
            try { DesktopIntegration.CreateForCurrentUser(); return 0; }
            catch (Exception error) { MessageBox.Show("无法创建桌面快捷方式：" + error.Message); return 1; }
        }
        if (args.Contains("--install-only") || args.Contains("--serve-only") || args.Contains("--diagnose")) {
            try {
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
                var engine = new Engine(root, (n, message) => Console.WriteLine(n + "% " + message), Console.WriteLine);
                if (args.Contains("--diagnose")) { Console.WriteLine(engine.HardwareCheck(false)); return 0; }
                if (args.Contains("--install-only")) {
                    engine.Setup(CancellationToken.None);
                    try { Console.WriteLine("桌面快捷方式：" + DesktopIntegration.CreateForCurrentUser()); }
                    catch (Exception error) { Console.Error.WriteLine("无法创建桌面快捷方式：" + error.Message); }
                    return 0;
                }
                int port = 7860;
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--port") port = int.Parse(args[++i]);
                using (Process server = engine.StartServer(port, CancellationToken.None)) { Console.WriteLine("@@READY " + engine.AppUrl); server.WaitForExit(); return server.ExitCode; }
            } catch (Exception error) { Console.Error.WriteLine(error.ToString()); return 1; }
        }
        if (File.Exists(Path.Combine(root, ".runtime", "update-transaction.json"))) {
            var recovery = new Engine(root, (n, message) => {}, message => {});
            try { recovery.HandoffUpdate(true); return 0; }
            catch (Exception error) { MessageBox.Show("更新恢复未完成：" + error.Message); return 1; }
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        // A second double-click reopens the existing app instead of starting another server.
        string key = DesktopIntegration.InstanceKey(root);
        using (var mutex = new Mutex(false, key))
        using (var openSignal = new EventWaitHandle(false, EventResetMode.AutoReset, key + "-open")) {
            bool owns = false;
            try {
                try { owns = mutex.WaitOne(0); } catch (AbandonedMutexException) { owns = true; }
                if (!owns) { openSignal.Set(); return 0; }
                Application.Run(new LauncherForm(root, args.Contains("--open"), openSignal));
            } finally { if (owns) mutex.ReleaseMutex(); }
        }
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
    private string gpuIdentity;
    private const string Revision = "windows-setup-1";
    private const string PreviousFfmpegUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-essentials_build.zip";
    private const string FfmpegMirrorUrl = "https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/ffmpeg-8.1.2-essentials_build.zip";
    private static readonly TimeSpan DownloadIdleTimeout = TimeSpan.FromSeconds(45);
    internal Engine(string root, Action<int, string> progress, Action<string> logger) {
        Root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Runtime = Path.Combine(Root, ".runtime"); report = progress; log = logger;
    }
    internal string BasePython { get { return Path.Combine(Runtime, "python", "tools", "python.exe"); } }
    private string Python(string env) { return Path.Combine(Runtime, env, "Scripts", "python.exe"); }
    private string Tool(string name) {
        string folder = Path.Combine(Runtime, "ffmpeg");
        if (!Directory.Exists(folder)) return null;
        string bin = FindFfmpegBin(folder);
        return bin == null ? null : Path.Combine(bin, name + ".exe");
    }
    internal string LogPath { get { return Path.Combine(Runtime, "setup.log"); } }
    internal void WriteLog(string message) {
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
        string cache = Environment.GetEnvironmentVariable("MODEL_CACHE");
        if (String.IsNullOrEmpty(cache)) cache = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "VoiceStudios", "models");
        env["HF_HOME"] = Path.Combine(cache, "huggingface");
        env["HF_HUB_CACHE"] = Path.Combine(cache, "huggingface", "hub");
        env["MODEL_CACHE"] = cache; env["TORCH_HOME"] = Path.Combine(cache, "torch");
        env["NUMBA_CACHE_DIR"] = Path.Combine(cache, "numba"); env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1";
        env["VOICE_LAUNCHER_PID"] = Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture);
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
            var timer = Stopwatch.StartNew();
            try {
                while (!p.WaitForExit(300)) {
                    token.ThrowIfCancellationRequested();
                    if (timer.Elapsed.TotalMinutes > minutes) throw new TimeoutException("This setup step took too long. Check the internet connection and try again.");
                }
                p.WaitForExit();
                token.ThrowIfCancellationRequested();
                if (p.ExitCode != 0) throw new InvalidOperationException("A setup check or package install failed. Open the setup log for details, then choose Repair setup.");
            } catch { KillTree(p); throw; }
        }
    }
    internal static void KillTree(Process p) {
        try {
            if (p == null || p.HasExited) return;
            using (var killer = Process.Start(new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "taskkill.exe"), "/PID " + p.Id + " /T /F") {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
            })) { killer.WaitForExit(15000); }
        } catch (InvalidOperationException) { } catch (System.ComponentModel.Win32Exception) { }
    }
    internal string HardwareCheck(bool disk) {
        if (!Environment.Is64BitOperatingSystem || !Environment.Is64BitProcess) throw new InvalidOperationException("请使用 64 位 Windows 10 或 11。");
        if (!File.Exists(Path.Combine(Root, "app.py")) || !File.Exists(Path.Combine(Root, "windows", "runtime-pins.json")))
            throw new InvalidOperationException("请先完整解压 ZIP，保持启动器与 app.py、windows 文件夹在同一目录。");
        var info = new ProcessStartInfo("nvidia-smi", "--query-gpu=index,name,memory.total,driver_version,uuid,pci.bus_id --format=csv,noheader,nounits") {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };
        string output;
        try { using (Process p = Process.Start(info)) {
            output = p.StandardOutput.ReadToEnd();
            if (!p.WaitForExit(15000) || p.ExitCode != 0) throw new InvalidOperationException("显卡检查失败，请更新 NVIDIA 驱动后重启电脑。");
        }} catch (System.ComponentModel.Win32Exception) { throw new InvalidOperationException("需要 NVIDIA 显卡及可用驱动，最低为 6 GB 级显存。"); }
        int best = 0; string summary = "";
        gpuIdentity = null;
        foreach (string line in output.Split(new[] {'\r','\n'}, StringSplitOptions.RemoveEmptyEntries)) {
            string[] parts = line.Split(','); int index, memory;
            if (parts.Length >= 4 && int.TryParse(parts[0].Trim(), out index) && int.TryParse(parts[2].Trim(), out memory) && memory > best) {
                gpuIdentity = parts.Length >= 6 ? line.Trim() : null;
                best = memory; gpuIndex = index; summary = parts[1].Trim() + " · " + (memory / 1024.0).ToString("0.0", CultureInfo.InvariantCulture) + " GB · driver " + parts[3].Trim();
            }
        }
        if (best < 5500) throw new InvalidOperationException("需要 6 GB 级或以上 NVIDIA 显卡。检测到的显存不足。");
        if (disk) {
            var drive = new DriveInfo(Path.GetPathRoot(Root));
            if (drive.AvailableFreeSpace < 30L * 1024 * 1024 * 1024) throw new InvalidOperationException("安装前请在程序所在磁盘预留至少 30 GB 可用空间。");
        }
        return summary;
    }
    private static string Sha(string path) { using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant(); }
    private string Fingerprint(bool previousFfmpegUrl = false) {
        var text = new StringBuilder(Revision + Path.GetFullPath(Root).ToUpperInvariant());
        foreach (string name in new[] {"requirements-ui.txt", "requirements-singing.txt", "requirements-tts.txt", "windows/runtime-pins.json", "windows/check_install.py"}) {
            string path = Path.Combine(Root, name);
            if (previousFfmpegUrl && name == "windows/runtime-pins.json") {
                // The mirror has the very same pinned bytes. Preserve completed installs.
                string pins = Encoding.UTF8.GetString(File.ReadAllBytes(path)).Replace(FfmpegMirrorUrl, PreviousFfmpegUrl);
                using (var sha = SHA256.Create())
                    text.Append(BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(pins))).Replace("-", "").ToLowerInvariant());
            } else text.Append(Sha(path));
        }
        using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(Encoding.UTF8.GetBytes(text.ToString()))).Replace("-", "");
    }
    internal bool IsReady() {
        try {
            if (!File.Exists(Path.Combine(Runtime, "ready.json"))) return false;
            var data = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Runtime, "ready.json")));
            string fingerprint = (string)data["fingerprint"];
            return (fingerprint == Fingerprint() || fingerprint == Fingerprint(true)) &&
                HasPython(Path.Combine(Runtime, "python")) && File.Exists(Python("ui")) &&
                File.Exists(Python("singing")) && File.Exists(Python("speech")) && Tool("ffmpeg") != null;
        } catch { return false; }
    }
    internal string Download(string dependency, Dictionary<string, object> pin, CancellationToken token, int progress, TimeSpan idleTimeout) {
        token.ThrowIfCancellationRequested();
        string folder = Path.Combine(Runtime, "downloads"); Directory.CreateDirectory(folder);
        string file = Path.Combine(folder, Path.GetFileName((string)pin["file"]));
        string expected = (string)pin["sha256"];
        string url = (string)pin["url"];
        if (File.Exists(file) && String.Equals(Sha(file), expected, StringComparison.OrdinalIgnoreCase)) {
            token.ThrowIfCancellationRequested();
            WriteLog("复用已校验下载：" + dependency);
            return file;
        }
        string partial = file + ".partial";
        WriteLog("下载 " + dependency + "：" + url);
        try {
            using (var client = new HttpClient { Timeout = Timeout.InfiniteTimeSpan })
            using (var request = CancellationTokenSource.CreateLinkedTokenSource(token)) {
                client.DefaultRequestHeaders.UserAgent.ParseAdd("WangVoiceStudio/0.5");
                try {
                    request.CancelAfter(idleTimeout);
                    using (var response = client.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, request.Token).GetAwaiter().GetResult()) {
                        if (!response.IsSuccessStatusCode) {
                            string http = "HTTP " + (int)response.StatusCode + " " + response.ReasonPhrase;
                            WriteLog(dependency + " " + http + " · " + url);
                            string next = response.StatusCode == HttpStatusCode.Forbidden
                                ? "请确认当前网络允许此下载，受管理的电脑请联系管理员。"
                                : response.StatusCode == HttpStatusCode.NotFound
                                  ? "下载地址不可用，请检查是否有更新的安装包。"
                                  : "请检查网络后点击「修复安装」。";
                            throw new InvalidOperationException(dependency + " 下载失败（" + http + "）。" + next);
                        }
                        long? total = response.Content.Headers.ContentLength;
                        long done = 0;
                        var timer = Stopwatch.StartNew();
                        // Closing the response also interrupts .NET Framework streams that ignore
                        // cancellation after a streamed read has already started.
                        using (request.Token.Register(response.Dispose))
                        using (var input = response.Content.ReadAsStreamAsync().GetAwaiter().GetResult())
                        using (var output = File.Create(partial)) {
                            var buffer = new byte[128 * 1024];
                            while (true) {
                                request.CancelAfter(idleTimeout);
                                int count = input.ReadAsync(buffer, 0, buffer.Length, request.Token).GetAwaiter().GetResult();
                                request.Token.ThrowIfCancellationRequested();
                                if (count == 0) break;
                                output.Write(buffer, 0, count);
                                done += count;
                                if (timer.ElapsedMilliseconds > 600) {
                                    report(progress, "正在下载 " + dependency + " · " + (done / 1024 / 1024) +
                                        (total.HasValue ? "/" + (total.Value / 1024 / 1024) : "") + " MB");
                                    timer.Restart();
                                }
                            }
                        }
                        if (total.HasValue && done != total.Value)
                            throw new IOException("Content-Length mismatch: " + done + "/" + total.Value);
                    }
                } catch (Exception error) {
                    if (!(error is OperationCanceledException || error is IOException ||
                        error is HttpRequestException || error is WebException || error is ObjectDisposedException)) throw;
                    token.ThrowIfCancellationRequested();
                    if (request.IsCancellationRequested)
                        throw new TimeoutException(dependency + " 下载超时。请检查网络后点击「修复安装」。", error);
                    throw new IOException(dependency + " 下载未完成。请检查网络和磁盘可用空间，再点击「修复安装」。", error);
                }
            }
            token.ThrowIfCancellationRequested();
            if (!String.Equals(Sha(partial), expected, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException(dependency + " 的 SHA-256 校验失败。请点击「修复安装」重新下载。");
            token.ThrowIfCancellationRequested();
            if (File.Exists(file)) File.Replace(partial, file, null);
            else File.Move(partial, file);
            return file;
        } catch (Exception error) {
            WriteLog(dependency + " · " + url + " · " + (token.IsCancellationRequested ? "下载已停止" : error.ToString()));
            throw;
        } finally {
            try { File.Delete(partial); }
            catch (IOException) {}
            catch (UnauthorizedAccessException) {}
        }
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
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            using (var input = entry.Open())
            using (var output = File.Create(path)) {
                byte[] buffer = new byte[128 * 1024];
                int count;
                while ((count = input.Read(buffer, 0, buffer.Length)) > 0) {
                    token.ThrowIfCancellationRequested();
                    output.Write(buffer, 0, count);
                }
            }
        }
    }
    private static bool HasPython(string folder) {
        string tools = Path.Combine(folder, "tools");
        return File.Exists(Path.Combine(tools, "python.exe")) &&
            File.Exists(Path.Combine(tools, "python312.dll")) &&
            File.Exists(Path.Combine(tools, "Lib", "venv", "__init__.py"));
    }
    internal static string FindFfmpegBin(string folder) {
        return Directory.EnumerateFiles(folder, "ffmpeg.exe", SearchOption.AllDirectories)
            .Select(Path.GetDirectoryName).FirstOrDefault(bin => File.Exists(Path.Combine(bin, "ffprobe.exe")));
    }
    internal void InstallArchive(string dependency, string archive, string destination, Func<string, bool> valid, CancellationToken token) {
        string previous = destination + ".previous";
        if (!Directory.Exists(destination) && Directory.Exists(previous)) Directory.Move(previous, destination);
        string staging = destination + ".staging";
        try {
            DeleteRuntimeTree(staging);
            Extract(archive, staging, token);
            if (!valid(staging)) throw new InvalidDataException(dependency + " 安装包缺少必要文件，请打开安装日志。");
            token.ThrowIfCancellationRequested();
            DeleteRuntimeTree(previous);
            if (Directory.Exists(destination)) Directory.Move(destination, previous);
            try { Directory.Move(staging, destination); }
            catch {
                if (Directory.Exists(previous)) Directory.Move(previous, destination);
                throw;
            }
        } finally {
            CleanupRuntimeTree(staging);
        }
        CleanupRuntimeTree(previous);
    }
    private void Pip(string python, string[] args, CancellationToken token) {
        Run(python, new[] {"-m", "pip", "install", "--no-input", "--progress-bar", "off", "--disable-pip-version-check", "--no-warn-script-location"}.Concat(args).ToArray(), token, 90);
    }
    private void DeleteRuntimeTree(string path) {
        string target = Path.GetFullPath(path);
        string boundary = Path.GetFullPath(Runtime).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!target.StartsWith(boundary, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Cache boundary rejected");
        if (!Directory.Exists(target)) return;
        CheckCacheTree(target);
        Directory.Delete(target, true);
    }
    private void CleanupRuntimeTree(string path) {
        try { DeleteRuntimeTree(path); }
        catch (IOException error) { WriteLog("安装临时文件暂未清理：" + error.Message); }
        catch (UnauthorizedAccessException error) { WriteLog("安装临时文件暂未清理：" + error.Message); }
    }
    private void CleanupInstallCaches() {
        CleanupRuntimeTree(Path.Combine(Runtime, "pip-cache"));
    }
    private static void CheckCacheTree(string directory) {
        if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) throw new IOException("Linked cache rejected");
        foreach (string file in Directory.EnumerateFiles(directory))
            if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0) throw new IOException("Linked cache entry rejected");
        foreach (string child in Directory.EnumerateDirectories(directory)) CheckCacheTree(child);
    }
    private void CompactRuntime(CancellationToken token, bool once = false) {
        var args = new List<string> {Path.Combine(Root, "windows", "compact_runtime.py"), "--root", Root};
        if (once) args.Add("--once");
        Run(BasePython, args.ToArray(), token, 2);
    }
    internal FileStream AcquireSetupLock() {
        Directory.CreateDirectory(Runtime);
        try { return new FileStream(Path.Combine(Runtime, "setup.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException error) {
            int code = error.HResult & 0xffff;
            if (code != 32 && code != 33) throw;
            throw new InvalidOperationException("此文件夹已有安装正在进行，请返回原来的安装窗口。", error);
        }
    }
    internal void Setup(CancellationToken token) {
        using (var setupLock = AcquireSetupLock()) {
            token.ThrowIfCancellationRequested();
            Stage(2, "正在检查显卡和可用空间…"); WriteLog(HardwareCheck(true));
            string readyMarker = Path.Combine(Runtime, "ready.json");
            var pins = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Root, "windows", "runtime-pins.json")));
            string pythonFolder = Path.Combine(Runtime, "python");
            if (!HasPython(pythonFolder)) {
                Stage(5, "正在准备独立 Python 环境…");
                string archive = Download("Python", (Dictionary<string, object>)pins["python"], token, 8, DownloadIdleTimeout);
                InstallArchive("Python", archive, pythonFolder, HasPython, token);
            }
            if (Tool("ffmpeg") == null) {
                Stage(12, "正在准备音视频工具…");
                string archive = Download("FFmpeg", (Dictionary<string, object>)pins["ffmpeg"], token, 15, DownloadIdleTimeout);
                InstallArchive("FFmpeg", archive, Path.Combine(Runtime, "ffmpeg"), folder => FindFfmpegBin(folder) != null, token);
            }
            Run(BasePython, new[] {Path.Combine(Root, "windows", "restore_references.py"), "--root", Root, "--ffmpeg", Tool("ffmpeg")}, token, 2);
            Stage(20, "正在安装 GPU 运行库，下载较大，请保持此窗口开启。");
            Pip(BasePython, new[] {"numpy==1.26.4"}, token);
            Pip(BasePython, new[] {"torch==2.7.1", "torchaudio==2.7.1", "--index-url", "https://download.pytorch.org/whl/cu128"}, token);
            Stage(40, "正在创建独立应用环境…");
            foreach (string env in new[] {"ui", "singing", "speech"}) {
                string config = Path.Combine(Runtime, env, "pyvenv.cfg");
                bool exists = File.Exists(Python(env));
                bool correctHome = File.Exists(config) && File.ReadAllText(config).IndexOf("home = " + Path.GetDirectoryName(BasePython), StringComparison.OrdinalIgnoreCase) >= 0;
                if (exists && correctHome) continue;
                var args = new List<string> {"-m", "venv"}; if (exists) args.Add("--upgrade"); if (env != "ui") args.Add("--system-site-packages"); args.Add(Path.Combine(Runtime, env));
                Run(BasePython, args.ToArray(), token, 10);
            }
            Stage(48, "正在安装中文界面…"); Pip(Python("ui"), new[] {"-r", Path.Combine(Root, "requirements-ui.txt")}, token);
            Stage(62, "正在安装翻唱工具…"); Pip(Python("singing"), new[] {"-r", Path.Combine(Root, "requirements-singing.txt")}, token);
            Stage(78, "正在安装文字语音工具…"); Pip(Python("speech"), new[] {"-r", Path.Combine(Root, "requirements-tts.txt")}, token);
            Stage(90, "正在验证 GPU 和已安装组件…");
            string doctor = Path.Combine(Root, "windows", "check_install.py");
            ValidateGpu(token, force: true);
            Run(BasePython, new[] {doctor, "tools"}, token, 2);
            Run(Python("ui"), new[] {doctor, "ui"}, token, 5);
            Run(Python("singing"), new[] {doctor, "singing"}, token, 5);
            Run(Python("speech"), new[] {doctor, "speech"}, token, 5);
            CompactRuntime(token);
            CleanupInstallCaches();
            token.ThrowIfCancellationRequested();
            string temporary = readyMarker + ".tmp";
            File.WriteAllText(temporary, json.Serialize(new { fingerprint = Fingerprint(), created_utc = DateTime.UtcNow.ToString("o"), version = Revision }));
            if (File.Exists(readyMarker)) File.Replace(temporary, readyMarker, null);
            else File.Move(temporary, readyMarker);
            Stage(100, "安装完成，可以打开工作室。");
        }
    }
    private static int FindPort(int start) {
        for (int port = start; port < start + 100; port++) {
            var listener = new TcpListener(IPAddress.Loopback, port);
            try { listener.Start(); return port; } catch (SocketException) { } finally { listener.Stop(); }
        }
        throw new InvalidOperationException("No free local app port was found. Close other copies of the app and try again.");
    }
    internal void HandoffUpdate(bool recover) {
        if (!File.Exists(BasePython)) throw new InvalidOperationException("请重新下载并解压完整安装包。");
        var info = ProcessInfo(BasePython, new[] {Path.Combine(Root, "studio_update.py"), recover ? "recover" : "run-request", "--root", Root, "--wait-pid", Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture)});
        info.StandardOutputEncoding = null; info.StandardErrorEncoding = null;
        info.RedirectStandardOutput = false; info.RedirectStandardError = false;
        Process.Start(info);
    }

    private string GpuValidationKey() {
        if (String.IsNullOrEmpty(gpuIdentity)) return null;
        var state = new StringBuilder(Fingerprint()).Append('|').Append(gpuIdentity);
        string torch = Path.Combine(Runtime, "python", "tools", "Lib", "site-packages", "torch");
        foreach (string path in new[] {BasePython, Path.Combine(torch, "version.py"),
                                      Path.Combine(torch, "lib", "torch_cuda.dll"),
                                      Path.Combine(torch, "lib", "c10_cuda.dll")}) {
            var file = new FileInfo(path);
            if (!file.Exists) return null;
            state.Append('|').Append(file.Length).Append('|').Append(file.LastWriteTimeUtc.Ticks);
        }
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(state.ToString())));
    }

    private void ValidateGpu(CancellationToken token, bool force = false) {
        token.ThrowIfCancellationRequested();
        string marker = Path.Combine(Runtime, "startup-gpu-validation-v1.txt");
        string key = null;
        try {
            key = GpuValidationKey();
            if (!force && key != null && File.Exists(marker) &&
                    String.Equals(File.ReadAllText(marker), key, StringComparison.Ordinal)) {
                WriteLog("沿用已通过的 CUDA 验证。");
                return;
            }
        } catch (IOException) { key = null; }
        catch (UnauthorizedAccessException) { key = null; }
        // This runs a real CUDA operation after setup, or if the GPU, driver or private runtime changes.
        Run(BasePython, new[] {Path.Combine(Root, "windows", "check_install.py"), "gpu"}, token, 5);
        if (key == null) return;
        string temporary = marker + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            if (!String.Equals(GpuValidationKey(), key, StringComparison.Ordinal)) return;
            File.WriteAllText(temporary, key, new UTF8Encoding(false));
            if (File.Exists(marker)) File.Replace(temporary, marker, null);
            else File.Move(temporary, marker);
        } catch (IOException) {}
        catch (UnauthorizedAccessException) {}
        finally {
            try { File.Delete(temporary); } catch (IOException) {} catch (UnauthorizedAccessException) {}
        }
    }

    internal Process StartServer(int startPort, CancellationToken token) {
        if (!IsReady()) throw new InvalidOperationException("安装尚未完成，请先点击「安装并打开工作室」或「修复安装」。");
        Stage(100, "正在检查显卡…"); WriteLog(HardwareCheck(false));
        int port = FindPort(startPort);
        // Load Gradio while the launcher checks CUDA, references and old caches.
        // The child only starts accepting jobs after it receives the readiness byte.
        const string bootstrap = "import gradio, runpy, sys\n"
            + "if sys.stdin.buffer.read(1) != b'1': sys.exit(1)\n"
            + "runpy.run_path('app.py', run_name='__main__')";
        var info = ProcessInfo(Python("ui"), new[] {"-c", bootstrap});
        info.RedirectStandardInput = true;
        info.EnvironmentVariables["PORT"] = port.ToString(CultureInfo.InvariantCulture);
        Process server = new Process { StartInfo = info, EnableRaisingEvents = true };
        string appLog = Path.Combine(Runtime, "app.log");
        DataReceivedEventHandler receive = (sender, e) => { if (e.Data != null) { lock (logLock) File.AppendAllText(appLog, e.Data + Environment.NewLine, Encoding.UTF8); log(e.Data); } };
        server.OutputDataReceived += receive; server.ErrorDataReceived += receive;
        server.Start(); server.BeginOutputReadLine(); server.BeginErrorReadLine();
        AppUrl = "http://127.0.0.1:" + port;
        try {
            string legacyCache = Path.Combine(Root, ".cache");
            if (Directory.Exists(legacyCache))
                Run(BasePython, new[] {Path.Combine(Root, "studio_paths.py"), "migrate-cache", legacyCache}, token, 10);
            ValidateGpu(token);
            Run(BasePython, new[] {Path.Combine(Root, "windows", "restore_references.py"), "--root", Root, "--ffmpeg", Tool("ffmpeg")}, token, 2);
            if (!File.Exists(Path.Combine(Runtime, "compact-runtime-v2.json")))
                CompactRuntime(token, true);
            token.ThrowIfCancellationRequested();
            server.StandardInput.Write("1");
            server.StandardInput.Close();
        } catch { KillTree(server); server.Dispose(); throw; }
        Stage(100, "正在打开本地界面…");
        using (var client = new HttpClient(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(2) }) {
            var timer = Stopwatch.StartNew();
            try {
                while (timer.Elapsed.TotalMinutes < 3) {
                    token.ThrowIfCancellationRequested();
                    if (server.HasExited) throw new InvalidOperationException("界面启动失败，请查看 app.log 或点击「修复安装」。");
                    try { if (client.GetAsync(AppUrl, token).GetAwaiter().GetResult().IsSuccessStatusCode) { Stage(100, "工作室已就绪。"); return server; } }
                    catch (HttpRequestException) { } catch (TaskCanceledException) { token.ThrowIfCancellationRequested(); }
                    token.WaitHandle.WaitOne(90);
                }
                throw new TimeoutException("界面启动超时，请查看 app.log 或尝试修复安装。");
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
        // Real cache cleanup in an isolated fixture; model/runtime sentinels survive.
        string fixture = Path.Combine(root, "work", "cache-test-" + Guid.NewGuid().ToString("N"));
        var testEngine = new Engine(fixture, (n, message) => {}, message => {});
        foreach (string dir in new[] {"pip-cache", "downloads", "python"}) {
            string path = Path.Combine(testEngine.Runtime, dir);
            Directory.CreateDirectory(path); File.WriteAllText(Path.Combine(path, "sentinel"), "keep");
        }
        Directory.CreateDirectory(Path.Combine(fixture, ".cache"));
        File.WriteAllText(Path.Combine(fixture, ".cache", "model"), "keep");
        testEngine.CleanupInstallCaches();
        if (Directory.Exists(Path.Combine(testEngine.Runtime, "pip-cache"))) return 5;
        if (!File.Exists(Path.Combine(testEngine.Runtime, "python", "sentinel")) ||
            !File.Exists(Path.Combine(testEngine.Runtime, "downloads", "sentinel")) ||
            !File.Exists(Path.Combine(fixture, ".cache", "model"))) return 6;
        Directory.Delete(fixture, true);
        Console.WriteLine("Windows arguments, archive boundaries and selective cache cleanup passed."); return 0;
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
    private readonly LinkLabel desktopLink = new LinkLabel();
    private CancellationTokenSource cancel;
    private Process server;
    private StudioWindow desktopWindow;
    private bool busy;
    private bool closeAfterCancellation;
    private string lastWorkError;
    private readonly System.Windows.Forms.Timer openTimer = new System.Windows.Forms.Timer();
    internal LauncherForm(string root, bool autoOpen, EventWaitHandle openSignal) {
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        Text = "王洪文语音工作室"; Size = new Size(820, 630); MinimumSize = new Size(760, 580); StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(248, 246, 242); Font = new Font("Segoe UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
        var title = new Label { Text = "王洪文语音工作室", Font = new Font("Segoe UI", 26, FontStyle.Bold), ForeColor = Color.FromArgb(36, 43, 43), Location = new Point(30, 22), Size = new Size(700, 54) };
        var subtitle = new Label { UseMnemonic = false, Text = "AI 歌曲翻唱与文字语音 · 6 GB 起步，自动选择性能档位", Location = new Point(34, 80), Size = new Size(700, 27), ForeColor = Color.FromArgb(115, 62, 50) };
        hardware.SetBounds(34, 121, 730, 42); hardware.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right; hardware.ForeColor = Color.FromArgb(90, 100, 95); hardware.Text = "Windows 10/11 · NVIDIA 6 GB 显存起步 · 首次安装前预留 30 GB 可用空间";
        status.SetBounds(34, 175, 730, 52); status.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right; status.Font = new Font("Segoe UI", 12, FontStyle.Bold);
        progress.SetBounds(34, 233, 730, 15); progress.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        var hint = new Label { Text = "装好并缓存完整模型后约占 11 GB，随缓存和结果变化。\n首次安装前需有 30 GB 可用空间（含临时文件），装好后自动清理。", Location = new Point(34, 263), Size = new Size(730, 52), ForeColor = Color.FromArgb(103, 112, 109), Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right };
        primary.SetBounds(34, 329, 300, 44); primary.UseMnemonic = false; primary.BackColor = Color.FromArgb(158, 57, 46); primary.ForeColor = Color.White; primary.FlatStyle = FlatStyle.Flat;
        repair.SetBounds(350, 329, 180, 44); repair.Text = "修复安装"; repair.FlatStyle = FlatStyle.Flat;
        stop.SetBounds(546, 329, 150, 44); stop.Text = "停止"; stop.FlatStyle = FlatStyle.Flat; stop.Enabled = false;
        showDetail.SetBounds(34, 389, 300, 25); showDetail.Text = "显示安装详情";
        quickHelp.SetBounds(34, 428, 730, 100); quickHelp.Text = "工作室窗口打开后，输入文字或放入音频/视频，点击「一键生成」。\n高级选项通常无需修改。生成后可下载 MP3 或无损 FLAC。\n所有输出均为 AI 合成，并非真实录音。"; quickHelp.ForeColor = Color.FromArgb(103, 112, 109);
        detail.SetBounds(34, 425, 730, 104); detail.Multiline = true; detail.ScrollBars = ScrollBars.Vertical; detail.ReadOnly = true; detail.BackColor = Color.White; detail.Font = new Font("Consolas", 8); detail.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right; detail.Visible = false;
        showDetail.CheckedChanged += (sender, e) => { detail.Visible = showDetail.Checked; quickHelp.Visible = !showDetail.Checked; };
        var logs = new LinkLabel { Text = "打开安装日志", Location = new Point(34, 545), Size = new Size(190, 24), Anchor = AnchorStyles.Bottom | AnchorStyles.Left };
        logs.LinkClicked += (sender, e) => { if (File.Exists(engine.LogPath)) Process.Start(new ProcessStartInfo(engine.LogPath) { UseShellExecute = true }); };
        desktopLink.Text = "创建 / 修复桌面快捷方式";
        desktopLink.SetBounds(240, 545, 360, 24);
        desktopLink.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        desktopLink.LinkClicked += (sender, e) => EnsureDesktopShortcut(true);
        Controls.Add(desktopLink);
        Controls.AddRange(new Control[] {title, subtitle, hardware, status, progress, hint, primary, repair, stop, showDetail, quickHelp, detail, logs});
        engine = new Engine(root, UpdateProgress, AppendLog);
        RefreshButtons();
        primary.Click += async (sender, e) => { if (server != null && !server.HasExited) OpenApp(); else await BeginWork(!engine.IsReady()); };
        repair.Click += async (sender, e) => await BeginWork(true);
        stop.Click += (sender, e) => {
            if (busy) { RequestCancellation(); return; }
            if (lastWorkError != null) { Close(); return; }
            CloseApp(); Engine.KillTree(server); server = null; RefreshButtons();
        };
        FormClosing += (sender, e) => {
            if (busy) {
                e.Cancel = true;
                if (closeAfterCancellation || MessageBox.Show(this, "要停止当前操作并关闭吗？之后可以继续安装。", Text, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
                closeAfterCancellation = true;
                RequestCancellation();
                return;
            }
            CloseApp(); Engine.KillTree(server);
        };
        openTimer.Interval = 350;
        openTimer.Tick += async (sender, e) => {
            if (!busy && File.Exists(Path.Combine(engine.Runtime, "update-request.json"))) {
                openTimer.Stop();
                try {
                    CloseApp(); Engine.KillTree(server); server = null;
                    engine.HandoffUpdate(false); Close();
                } catch (Exception error) {
                    File.Delete(Path.Combine(engine.Runtime, "update-request.json"));
                    status.Text = "更新未开始：" + error.Message; openTimer.Start();
                }
                return;
            }
            if (openSignal.WaitOne(0)) await OpenFromShortcut();
        };
        FormClosed += (sender, e) => openTimer.Dispose();
        Shown += async (sender, e) => {
            EnsureDesktopShortcut(false);
            openTimer.Start();
            if (autoOpen && engine.IsReady()) { await OpenFromShortcut(); return; }
            try { string text = await Task.Run(() => engine.HardwareCheck(false)); hardware.Text = text; }
            catch (Exception error) { hardware.Text = error.Message; }
        };
    }
    private void EnsureDesktopShortcut(bool notify, bool warnOnFailure = false) {
        try {
            string path = DesktopIntegration.CreateForCurrentUser();
            desktopLink.Text = "桌面快捷方式已就绪 · 点击查看";
            if (notify) MessageBox.Show(this, "双击桌面图标打开工作室。\n\n" + path +
                                        "\n\n请保留解压后的完整程序文件夹。",
                                        Text, MessageBoxButtons.OK, MessageBoxIcon.Information);
        } catch (Exception error) {
            desktopLink.Text = "桌面快捷方式未创建 · 点击重试";
            AppendLog(desktopLink.Text + "：" + error.Message);
            if (notify || warnOnFailure)
                MessageBox.Show(this, "无法创建桌面快捷方式。\n\n" + error.Message +
                                "\n\n仍可运行解压后的启动程序。",
                                Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
    private async Task OpenFromShortcut() {
        if (desktopWindow != null) { desktopWindow.BringToUser(); return; }
        if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
        Show(); Activate();
        if (busy) return;
        if (server != null && !server.HasExited) OpenApp();
        else if (engine.IsReady()) await BeginWork(false);
    }
    private void RefreshButtons() {
        if (busy) {
            primary.Enabled = false; repair.Enabled = false;
            stop.Text = "停止"; stop.Enabled = !cancel.IsCancellationRequested;
            return;
        }
        bool running = server != null && !server.HasExited;
        bool ready = !running && engine.IsReady();
        primary.Enabled = true; primary.Text = running ? "打开工作室窗口" : ready ? "打开工作室" : "安装并打开工作室";
        repair.Enabled = !running; stop.Enabled = running || lastWorkError != null;
        stop.Text = lastWorkError == null ? "停止" : "关闭";
        if (!running) status.Text = lastWorkError ?? (ready ? "已就绪，可以打开。" : "欢迎，首次使用请安装工作室。");
    }
    private void RequestCancellation() {
        if (cancel == null || cancel.IsCancellationRequested) return;
        stop.Enabled = false;
        status.Text = "正在停止…";
        cancel.Cancel();
    }
    private void UpdateProgress(int value, string text) {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { try { BeginInvoke(new Action<int, string>(UpdateProgress), value, text); } catch (InvalidOperationException) { } return; }
        if (cancel != null && cancel.IsCancellationRequested) return;
        progress.Value = Math.Max(0, Math.Min(100, value)); status.Text = text;
        if (desktopWindow != null) desktopWindow.ShowStartupProgress(text);
    }
    private void AppendLog(string text) {
        if (IsDisposed || Disposing) return;
        if (InvokeRequired) { try { BeginInvoke(new Action<string>(AppendLog), text); } catch (InvalidOperationException) { } return; }
        if (detail.TextLength > 60000) detail.Text = detail.Text.Substring(detail.TextLength - 30000);
        detail.AppendText(text + Environment.NewLine);
    }
    private void CloseApp() {
        StudioWindow window = desktopWindow;
        desktopWindow = null;
        if (window != null) window.Close();
    }
    private StudioWindow ShowStudioWindow() {
        if (desktopWindow != null) return desktopWindow;
        var window = new StudioWindow(Text, Icon, Path.Combine(engine.Runtime, "webview2"), AppendLog);
        desktopWindow = window;
        window.FormClosed += (sender, e) => {
            if (desktopWindow != window) return;
            desktopWindow = null;
            if (window.Ready) Close();
            else {
                if (busy) RequestCancellation();
                Show(); Activate();
            }
        };
        window.Show();
        Hide();
        return window;
    }
    private void OpenApp() {
        if (String.IsNullOrEmpty(engine.AppUrl)) return;
        var window = ShowStudioWindow();
        window.NavigateTo(engine.AppUrl);
        window.BringToUser();
    }
    private async Task BeginWork(bool setup) {
        if (busy) return;
        lastWorkError = null;
        cancel = new CancellationTokenSource();
        busy = true; RefreshButtons();
        try {
            if (setup) {
                await Task.Run(() => engine.Setup(cancel.Token));
                cancel.Token.ThrowIfCancellationRequested();
                EnsureDesktopShortcut(false, warnOnFailure: true);
            }
            ShowStudioWindow();
            await Task.Run(() => {
                if (!File.Exists(Path.Combine(engine.Runtime, "update-request.json")))
                    server = engine.StartServer(7860, cancel.Token);
            });
            cancel.Token.ThrowIfCancellationRequested();
            if (server != null && !server.HasExited) OpenApp();
        } catch (OperationCanceledException) { lastWorkError = "已停止，可以点击「修复安装」继续。"; }
        catch (Exception error) {
            lastWorkError = error is UnauthorizedAccessException
                ? "无法写入安装目录。请完整解压到有写入权限的文件夹，或联系管理员。"
                : error.Message;
            try { engine.WriteLog(error.ToString()); }
            catch (IOException) { AppendLog(error.ToString()); }
            catch (UnauthorizedAccessException) { AppendLog(error.ToString()); }
        }
        try {
            if (server == null || server.HasExited || lastWorkError != null) {
                CloseApp();
                if (server != null && !server.HasExited) {
                    Process current = server;
                    await Task.Run(() => Engine.KillTree(current));
                    server = null;
                }
                if (!closeAfterCancellation && !IsDisposed) Show();
            }
        } finally {
            busy = false;
            cancel.Dispose(); cancel = null;
            if (closeAfterCancellation) Close();
            else {
                RefreshButtons();
                if (lastWorkError != null) showDetail.Checked = true;
            }
        }
    }
}
