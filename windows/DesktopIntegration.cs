// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Security.Cryptography;
using System.Text;

internal static class DesktopIntegration {
    internal const string ShortcutName = "王洪文语音工作室";
    private const string OpenArgument = "--open";
    private const uint ShellItemCreated = 0x00000002;
    private const uint ShellItemUpdated = 0x00002000;
    private const uint ShellUnicodePath = 0x0005;

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern void SHChangeNotify(uint change, uint flags, string path, IntPtr reserved);

    // IShellLinkW vtable order is defined by the Windows Shell SDK.
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int length, IntPtr findData, uint flags);
        void GetIDList(out IntPtr item);
        void SetIDList(IntPtr item);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int length);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int length);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder arguments, int length);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
        void GetHotkey(out short shortcut);
        void SetHotkey(short shortcut);
        void GetShowCmd(out int command);
        void SetShowCmd(int command);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int length, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }

    private static IShellLinkW NewShellLink() {
        var shellLink = new Guid("00021401-0000-0000-C000-000000000046");
        return (IShellLinkW)Activator.CreateInstance(Type.GetTypeFromCLSID(shellLink, true));
    }

    private static bool SamePath(StringBuilder path, string expected) {
        return String.Equals(Environment.ExpandEnvironmentVariables(path.ToString()), expected,
                             StringComparison.OrdinalIgnoreCase);
    }

    private static bool Matches(string path, string executable, string icon = null) {
        if (!File.Exists(path)) return false;
        IShellLinkW link = NewShellLink();
        try {
            ((IPersistFile)link).Load(path, 0);
            var target = new StringBuilder(260);
            var arguments = new StringBuilder(64);
            link.GetPath(target, target.Capacity, IntPtr.Zero, 4); // SLGP_RAWPATH
            if (!SamePath(target, executable)) return false;
            link.GetArguments(arguments, arguments.Capacity);
            if (icon == null) return arguments.Length == 0 || arguments.ToString() == OpenArgument;

            var working = new StringBuilder(260);
            var iconLocation = new StringBuilder(260);
            int iconIndex;
            link.GetWorkingDirectory(working, working.Capacity);
            link.GetIconLocation(iconLocation, iconLocation.Capacity, out iconIndex);
            return SamePath(working, Path.GetDirectoryName(executable)) &&
                   arguments.ToString() == OpenArgument &&
                   iconIndex == 0 && SamePath(iconLocation, icon);
        } catch (COMException) {
            return false;
        } finally {
            Marshal.FinalReleaseComObject(link);
        }
    }

    private static string FindShortcut(string executable, string desktop) {
        string standardPath = Path.Combine(desktop, ShortcutName + ".lnk");
        if (File.Exists(standardPath)) return standardPath;
        foreach (string path in Directory.EnumerateFiles(desktop, "*.lnk")) {
            if (Matches(path, executable)) return path;
        }
        return standardPath;
    }

    private static string ShortcutIcon(string executable) {
        string root = Path.GetDirectoryName(executable);
        string asset = Path.Combine(root, "assets", "app-icon.ico");
        string fallback = File.Exists(asset) ? asset : executable;
        try {
            byte[] bytes;
            if (fallback == asset) {
                bytes = File.ReadAllBytes(asset);
            } else {
                using (Icon icon = Icon.ExtractAssociatedIcon(executable))
                using (var buffer = new MemoryStream()) {
                    if (icon == null) return executable;
                    icon.Save(buffer);
                    bytes = buffer.ToArray();
                }
            }

            // Explorer caches by icon path; changing the icon bytes changes the path.
            string digest;
            using (var sha = SHA256.Create())
                digest = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").Substring(0, 24);
            string cache = Path.Combine(root, ".runtime", "desktop-icons");
            string cachedIcon = Path.Combine(cache, digest + ".ico");
            if (File.Exists(cachedIcon)) return cachedIcon;
            Directory.CreateDirectory(cache);
            string temporary = Path.Combine(cache, Guid.NewGuid().ToString("N") + ".tmp");
            try {
                File.WriteAllBytes(temporary, bytes);
                try { File.Move(temporary, cachedIcon); }
                catch (IOException) {
                    if (!File.Exists(cachedIcon)) throw;
                }
            } finally {
                File.Delete(temporary);
            }
            return cachedIcon;
        } catch (IOException) {
            return fallback;
        } catch (UnauthorizedAccessException) {
            return fallback;
        }
    }

    internal static string Create(string executable, string desktop) {
        executable = Path.GetFullPath(executable);
        if (!File.Exists(executable)) throw new FileNotFoundException("找不到启动程序，请先完整解压安装包。", executable);
        if (String.IsNullOrWhiteSpace(desktop)) throw new IOException("无法找到当前用户的桌面文件夹。");
        Directory.CreateDirectory(desktop);
        string path = FindShortcut(executable, desktop);
        string icon = ShortcutIcon(executable);
        if (Matches(path, executable, icon)) return path;

        bool existing = File.Exists(path);
        IShellLinkW link = NewShellLink();
        try {
            link.SetPath(executable);
            link.SetArguments(OpenArgument);
            link.SetWorkingDirectory(Path.GetDirectoryName(executable));
            link.SetDescription(ShortcutName + " · 双击直接打开工作室");
            link.SetIconLocation(icon, 0);
            ((IPersistFile)link).Save(path, true);
        } finally {
            Marshal.FinalReleaseComObject(link);
        }
        if (!Matches(path, executable, icon)) throw new IOException("Windows 未能保存可打开的桌面快捷方式：" + path);
        SHChangeNotify(existing ? ShellItemUpdated : ShellItemCreated, ShellUnicodePath, path, IntPtr.Zero);
        return path;
    }

    internal static string CreateForCurrentUser() {
        string executable = Assembly.GetExecutingAssembly().Location;
        string root = Path.GetDirectoryName(executable);
        if (!File.Exists(Path.Combine(root, "app.py")) ||
            !File.Exists(Path.Combine(root, "windows", "runtime-pins.json")))
            throw new IOException("请先完整解压安装包，再运行解压后的启动程序。");
        string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory,
                                                   Environment.SpecialFolderOption.DoNotVerify);
        return Create(executable, desktop);
    }

    internal static string InstanceKey(string root) {
        using (var sha = SHA256.Create()) return "Local\\VoiceStudio-" + BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(root).TrimEnd('\\').ToUpperInvariant()))).Replace("-", "");
    }

    private static void SaveTestIcon(Icon icon, string asset) {
        using (var output = File.Create(asset)) icon.Save(output);
    }

    internal static int SelfTest(string root) {
        string fixture = Path.Combine(root, "work", "快捷方式 " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixture);
        try {
            string desktop = Path.Combine(fixture, "OneDrive", "桌面");
            string executable = Path.Combine(fixture, "中文 程序.exe");
            File.Copy(Assembly.GetExecutingAssembly().Location, executable);
            string assets = Path.Combine(fixture, "assets");
            Directory.CreateDirectory(assets);
            string asset = Path.Combine(assets, "app-icon.ico");
            SaveTestIcon(SystemIcons.Application, asset);

            string originalIcon = ShortcutIcon(executable);
            string path = Create(executable, desktop);
            if (!Matches(path, executable, originalIcon) || Path.GetDirectoryName(path) != desktop) return 20;
            File.SetLastWriteTimeUtc(path, new DateTime(2020, 1, 2));
            DateTime unchanged = File.GetLastWriteTimeUtc(path);
            if (Create(executable, desktop) != path || File.GetLastWriteTimeUtc(path) != unchanged) return 21;

            string renamed = Path.Combine(desktop, "保留我的快捷方式.lnk");
            File.Move(path, renamed);
            if (Create(executable, desktop) != renamed || Directory.GetFiles(desktop, "*.lnk").Length != 1) return 22;

            SaveTestIcon(SystemIcons.Warning, asset);
            string changedIcon = ShortcutIcon(executable);
            if (changedIcon == originalIcon || !File.Exists(changedIcon)) return 23;
            if (Create(executable, desktop) != renamed || !Matches(renamed, executable, changedIcon) ||
                Directory.GetFiles(desktop, "*.lnk").Length != 1) return 24;

            File.Delete(renamed);
            if (Create(executable, desktop) != path || !Matches(path, executable, changedIcon)) return 25;
            string moved = Path.Combine(fixture, "移动后 程序.exe");
            File.Move(executable, moved);
            if (Create(moved, desktop) != path || !Matches(path, moved, changedIcon)) return 26;

            File.Delete(asset);
            string embeddedIcon = ShortcutIcon(moved);
            if (!File.Exists(embeddedIcon) || Create(moved, desktop) != path || !Matches(path, moved, embeddedIcon)) return 27;
            Console.WriteLine("Missing links are restored, existing links are reused, and changed icons refresh in place.");
            return 0;
        } finally {
            Directory.Delete(fixture, true);
        }
    }
}
