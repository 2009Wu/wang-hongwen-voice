// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class InstallerTests {
    private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    private static readonly TimeSpan Wait = TimeSpan.FromSeconds(5);
    private static readonly byte[] Payload = Encoding.ASCII.GetBytes("verified fixture payload");
    private static Type engineType;
    private static Assembly launcher;
    private static string root;

    private sealed class HttpFixture : IDisposable {
        private readonly TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
        private readonly ManualResetEvent disposed = new ManualResetEvent(false);
        private readonly Task server;
        internal readonly string Url;

        internal HttpFixture(Action<NetworkStream, WaitHandle> send) {
            listener.Start();
            Url = "http://127.0.0.1:" + ((IPEndPoint)listener.LocalEndpoint).Port + "/archive.zip";
            server = Task.Run(() => {
                try {
                    using (var client = listener.AcceptTcpClient())
                    using (var stream = client.GetStream()) {
                        stream.ReadTimeout = 5000;
                        var reader = new StreamReader(stream, Encoding.ASCII);
                        string line;
                        while (!String.IsNullOrEmpty(line = reader.ReadLine())) {}
                        send(stream, disposed);
                    }
                } catch (SocketException) { if (!disposed.WaitOne(0)) throw; }
            });
        }

        internal static void Send(NetworkStream stream, string status, int length, byte[] bytes) {
            byte[] header = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + "\r\nContent-Length: " + length + "\r\nConnection: close\r\n\r\n");
            stream.Write(header, 0, header.Length);
            stream.Write(bytes, 0, bytes.Length);
        }

        public void Dispose() {
            disposed.Set();
            listener.Stop();
            Require(server.Wait(Wait), "HTTP fixture did not shut down");
            disposed.Dispose();
        }
    }

    private static void Require(bool condition, string message) {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static object Call(object instance, string method, params object[] args) {
        try { return instance.GetType().GetMethod(method, Instance).Invoke(instance, args); }
        catch (TargetInvocationException error) { ExceptionDispatchInfo.Capture(error.InnerException).Throw(); throw; }
    }

    private static void Expect<T>(Action test, string message) where T : Exception {
        try { test(); }
        catch (T error) {
            Require(error.Message.Contains(message), "Unexpected " + typeof(T).Name + ": " + error.Message);
            return;
        }
        throw new Exception("Expected " + typeof(T).Name + " " + message);
    }

    private static string SHA(byte[] bytes) {
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    private static Dictionary<string, object> Pin(string url, string filename, string hash) {
        return new Dictionary<string, object> { {"url", url}, {"file", filename}, {"sha256", hash} };
    }

    private static object Engine(string directory) {
        return Activator.CreateInstance(engineType, Instance, null, new object[] {
            directory, new Action<int, string>((n, msg) => {}), new Action<string>(msg => {})
        }, null);
    }

    private static void Downloads() {
        var engine = Engine(root);
        string downloads = Path.Combine(root, ".runtime", "downloads");
        string archive = Path.Combine(downloads, "ok.zip");
        Func<string, string, string, CancellationToken, TimeSpan, string> download =
            (url, name, hash, token, timeout) => (string)Call(engine, "Download", "FFmpeg", Pin(url, name, hash), token, 12, timeout);
        string hashOfPayload = SHA(Payload);

        foreach (string status in new[] {"404 Not Found", "403 Forbidden"}) {
            using (var http = new HttpFixture((stream, stopped) => HttpFixture.Send(stream, status, 0, new byte[0]))) {
                Expect<InvalidOperationException>(() => download(http.Url, "ok.zip", hashOfPayload, CancellationToken.None, Wait), "FFmpeg 下载失败（HTTP " + status);
                string log = File.ReadAllText(Path.Combine(root, ".runtime", "setup.log"));
                Require(log.Contains(http.Url) && log.Contains("HTTP " + status), "Failed HTTP response or URL missing from log");
                Require(!File.Exists(archive) && !File.Exists(archive + ".partial"), "HTTP failure published an archive");
            }
            Console.WriteLine("PASS HTTP " + status);
        }
        using (var http = new HttpFixture((stream, stopped) => {
            HttpFixture.Send(stream, "200 OK", 5000, new byte[] {1});
            stopped.WaitOne();
        })) {
            Expect<TimeoutException>(() => download(http.Url, "ok.zip", hashOfPayload, CancellationToken.None, TimeSpan.FromMilliseconds(500)), "FFmpeg 下载超时");
            Require(!File.Exists(archive + ".partial"), "Body timeout left a partial file");
        }
        using (var http = new HttpFixture((stream, stopped) => stopped.WaitOne())) {
            Expect<TimeoutException>(() => download(http.Url, "ok.zip", hashOfPayload, CancellationToken.None, TimeSpan.FromMilliseconds(500)), "FFmpeg 下载超时");
        }
        Console.WriteLine("PASS header and body inactivity timeout");

        using (var http = new HttpFixture((stream, stopped) => HttpFixture.Send(stream, "200 OK", Payload.Length + 400, Payload))) {
            Expect<IOException>(() => download(http.Url, "ok.zip", hashOfPayload, CancellationToken.None, Wait), "FFmpeg 下载未完成");
            Require(!File.Exists(archive) && !File.Exists(archive + ".partial"), "Interrupted download was retained");
        }
        Console.WriteLine("PASS interrupted transfer");

        using (var http = new HttpFixture((stream, stopped) => HttpFixture.Send(stream, "200 OK", Payload.Length, Payload))) {
            Expect<InvalidDataException>(() => download(http.Url, "ok.zip", SHA(new byte[0]), CancellationToken.None, Wait), "SHA-256 校验失败");
            Require(!File.Exists(archive) && !File.Exists(archive + ".partial"), "Bad checksum was retained");
        }
        Console.WriteLine("PASS checksum mismatch");

        using (var http = new HttpFixture((stream, stopped) => {
            HttpFixture.Send(stream, "200 OK", Payload.Length + 10000, Payload);
            stopped.WaitOne();
        }))
        using (var cancel = new CancellationTokenSource()) {
            var job = Task.Run(() => Expect<OperationCanceledException>(
                () => download(http.Url, "ok.zip", hashOfPayload, cancel.Token, TimeSpan.FromSeconds(30)), ""));
            Require(SpinWait.SpinUntil(() => File.Exists(archive + ".partial"), Wait), "Download never entered the body read");
            cancel.Cancel();
            Require(job.Wait(Wait), "Cancellation did not interrupt a stalled transfer");
            Require(!File.Exists(archive) && !File.Exists(archive + ".partial"), "Cancelled transfer was retained");
        }
        Console.WriteLine("PASS cancellation during download");

        File.WriteAllText(archive, "incomplete old archive");
        File.WriteAllText(archive + ".partial", "stale part");
        using (var http = new HttpFixture((stream, stopped) => HttpFixture.Send(stream, "200 OK", Payload.Length, Payload))) {
            Require(download(http.Url, "ok.zip", hashOfPayload, CancellationToken.None, Wait) == archive, "Retry did not publish a valid path");
            Require(SHA(File.ReadAllBytes(archive)) == hashOfPayload && !File.Exists(archive + ".partial"), "Retry did not replace damaged bytes");
        }
        Console.WriteLine("PASS valid transfer and retry after failed setup download");

        string oldUrl = "http://127.0.0.1:0/unused";
        Require(download(oldUrl, "ok.zip", hashOfPayload, CancellationToken.None, Wait) == archive, "Verified cache was not reused");
        using (var http = new HttpFixture((stream, stopped) => HttpFixture.Send(stream, "403 Forbidden", 0, new byte[0]))) {
            Expect<InvalidOperationException>(() => download(http.Url, "other.zip", hashOfPayload, CancellationToken.None, Wait), "HTTP 403");
            Require(SHA(File.ReadAllBytes(archive)) == hashOfPayload, "Another dependency failure damaged verified cache");
        }
        Console.WriteLine("PASS verified cache and preservation after failure");
    }

    private static string FindBin(string path) {
        return (string)engineType.GetMethod("FindFfmpegBin", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] {path});
    }

    private static void Tools(string archive) {
        var engine = Engine(root);
        string runtime = Path.Combine(root, ".runtime");
        string folder = Path.Combine(runtime, "ffmpeg");
        string fakeArchive = Path.Combine(root, "incomplete.zip");
        using (var zip = ZipFile.Open(fakeArchive, ZipArchiveMode.Create)) zip.CreateEntry("not-a-tool.txt");
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, "existing.txt"), "preserve on failed extraction");
        Func<string, bool> validate = path => FindBin(path) != null;
        Expect<InvalidDataException>(() => Call(engine, "InstallArchive", "FFmpeg", fakeArchive, folder, validate, CancellationToken.None), "缺少必要文件");
        Require(File.Exists(Path.Combine(folder, "existing.txt")) && !Directory.Exists(folder + ".staging"), "Failed extraction damaged existing directory");
        Call(engine, "InstallArchive", "FFmpeg", archive, folder, validate, CancellationToken.None);
        string bin = FindBin(folder);
        Require(bin != null && !Directory.Exists(folder + ".staging") && !Directory.Exists(folder + ".previous"), "Tools not committed after extraction");
        foreach (string tool in new[] {"ffmpeg.exe", "ffprobe.exe"}) {
            using (var process = Process.Start(new ProcessStartInfo(Path.Combine(bin, tool), "-version") {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true
            })) {
                string version = process.StandardOutput.ReadLine();
                Require(process.WaitForExit(10000) && process.ExitCode == 0 && version.Contains("8.1.2"), "Could not execute " + tool);
            }
        }
        Console.WriteLine("PASS atomic extraction, FFmpeg and FFprobe discovery and version");

        var other = Engine(root);
        using ((FileStream)Call(engine, "AcquireSetupLock")) {
            Expect<InvalidOperationException>(() => Call(other, "Setup", CancellationToken.None), "已有安装正在进行");
        }
        using (var retry = (FileStream)Call(other, "AcquireSetupLock")) Require(retry.CanWrite, "Installation lock not released for retry");
        Console.WriteLine("PASS exclusive setup lock and retry");
    }

    private static void FormRecovery() {
        string directory = Path.Combine(root, "launcher-fixture");
        var type = launcher.GetType("LauncherForm", true);
        using (var openSignal = new EventWaitHandle(false, EventResetMode.AutoReset))
        using (var form = (Form)Activator.CreateInstance(type, Instance, null, new object[] {directory, false, openSignal}, null))
        using (var timer = new System.Windows.Forms.Timer {Interval = 10}) {
            var stop = (Button)type.GetField("stop", Instance).GetValue(form);
            var repair = (Button)type.GetField("repair", Instance).GetValue(form);
            var primary = (Button)type.GetField("primary", Instance).GetValue(form);
            var status = (Label)type.GetField("status", Instance).GetValue(form);
            Exception error = null;
            timer.Tick += async (sender, evt) => {
                timer.Stop();
                try {
                    var cancel = new CancellationTokenSource();
                    type.GetField("cancel", Instance).SetValue(form, cancel);
                    type.GetField("busy", Instance).SetValue(form, true);
                    Call(form, "RefreshButtons");
                    Require(stop.Enabled && !repair.Enabled && !primary.Enabled, "Busy controls are wrong");
                    Call(stop, "OnClick", EventArgs.Empty);
                    Require(cancel.IsCancellationRequested && !stop.Enabled && status.Text == "正在停止…", "Stop button did not request cancellation");
                    type.GetField("busy", Instance).SetValue(form, false);
                    type.GetField("cancel", Instance).SetValue(form, null);
                    cancel.Dispose();

                    using (var setupLock = (FileStream)Call(Engine(directory), "AcquireSetupLock")) {
                        await (Task)Call(form, "BeginWork", true);
                        Require(repair.Enabled && primary.Enabled && stop.Enabled && stop.Text == "关闭", "Controls stayed disabled after failure");
                        Require(status.Text.Contains("已有安装正在进行"), "Original setup error was overwritten");
                        await (Task)Call(form, "BeginWork", true);
                        Require(repair.Enabled && stop.Enabled, "Retry left controls disabled");
                    }
                    Call(stop, "OnClick", EventArgs.Empty);
                    Require(form.IsDisposed, "Close button did not close the failed installer");
                } catch (Exception failure) { error = failure; }
                finally { if (!form.IsDisposed) form.Close(); Application.ExitThread(); }
            };
            timer.Start();
            Application.Run();
            if (error != null) throw error;
        }
        Console.WriteLine("PASS WinForms Stop, failure status, retry controls and close");
    }

    private static void ExistingInstallation() {
        string directory = Path.Combine(root, "completed");
        string runtime = Path.Combine(directory, ".runtime");
        string[] files = {
            "requirements-ui.txt", "requirements-singing.txt", "requirements-tts.txt",
            "windows/runtime-pins.json", "windows/check_install.py"
        };
        string mainFolder = Path.GetDirectoryName(launcher.Location);
        Directory.CreateDirectory(Path.Combine(directory, "windows"));
        string prefix = "windows-setup-1" + (directory + Path.DirectorySeparatorChar).ToUpperInvariant();
        foreach (string name in files) {
            string path = Path.Combine(directory, name);
            byte[] bytes = File.ReadAllBytes(Path.Combine(mainFolder, name));
            File.WriteAllBytes(path, bytes);
            if (name.EndsWith("runtime-pins.json")) {
                string text = Encoding.UTF8.GetString(bytes);
                const string mirror = "https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/";
                Require(text.Contains(mirror), "New mirror not present in bundled runtime pins");
                bytes = Encoding.UTF8.GetBytes(text.Replace(mirror, "https://www.gyan.dev/ffmpeg/builds/packages/"));
            }
            prefix += SHA(bytes);
        }
        foreach (string name in new[] {
            "python/tools/python.exe", "python/tools/python312.dll", "python/tools/Lib/venv/__init__.py",
            "ffmpeg/bin/ffmpeg.exe", "ffmpeg/bin/ffprobe.exe",
            "ui/Scripts/python.exe", "singing/Scripts/python.exe", "speech/Scripts/python.exe"
        }) {
            string path = Path.Combine(runtime, name);
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllText(path, "fixture");
        }
        string oldHash = SHA(Encoding.UTF8.GetBytes(prefix)).ToUpperInvariant();
        File.WriteAllText(Path.Combine(runtime, "ready.json"), "{\"fingerprint\":\"" + oldHash + "\"}");
        var engine = Engine(directory);
        Require((bool)Call(engine, "IsReady"), "An existing install would unnecessarily require setup");
        File.AppendAllText(Path.Combine(directory, "requirements-ui.txt"), "\n# changed requirements");
        Require(!(bool)Call(engine, "IsReady"), "Compatibility accepted altered requirements");
        Console.WriteLine("PASS existing ready marker survives mirror-only change");
    }

    [STAThread]
    private static int Main(string[] args) {
        Console.OutputEncoding = Encoding.UTF8;
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        root = args[2];
        launcher = Assembly.LoadFrom(args[0]);
        engineType = launcher.GetType("Engine", true);
        try {
            Downloads();
            Tools(args[1]);
            FormRecovery();
            ExistingInstallation();
            return 0;
        } catch (Exception error) {
            Console.Error.WriteLine(error);
            return 1;
        }
    }
}
