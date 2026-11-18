// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Security.Cryptography;
using System.Text;

internal static class DesktopIntegration {
    internal const string ShortcutName = "王洪文语音工作室";
    private const string OpenArgument = "--open";

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

    private static bool Matches(string path, string executable) {
        if (!File.Exists(path)) return false;
        IShellLinkW link = NewShellLink();
        try {
            ((IPersistFile)link).Load(path, 0);
            var target = new StringBuilder(260);
            var working = new StringBuilder(260);
            var arguments = new StringBuilder(64);
            link.GetPath(target, target.Capacity, IntPtr.Zero, 4); // SLGP_RAWPATH
            link.GetWorkingDirectory(working, working.Capacity);
            link.GetArguments(arguments, arguments.Capacity);
            return String.Equals(target.ToString(), executable, StringComparison.OrdinalIgnoreCase) &&
                   String.Equals(working.ToString(), Path.GetDirectoryName(executable), StringComparison.OrdinalIgnoreCase) &&
                   arguments.ToString() == OpenArgument;
        } catch (COMException) {
            return false;
        } finally {
            Marshal.FinalReleaseComObject(link);
        }
    }

    internal static string Create(string executable, string desktop) {
        executable = Path.GetFullPath(executable);
        if (!File.Exists(executable)) throw new FileNotFoundException("找不到启动程序，请先完整解压安装包。", executable);
        if (String.IsNullOrWhiteSpace(desktop)) throw new IOException("无法找到当前用户的桌面文件夹。");
        Directory.CreateDirectory(desktop);
        string path = Path.Combine(desktop, ShortcutName + ".lnk");
        if (Matches(path, executable)) return path;

        IShellLinkW link = NewShellLink();
        try {
            link.SetPath(executable);
            link.SetArguments(OpenArgument);
            link.SetWorkingDirectory(Path.GetDirectoryName(executable));
            link.SetDescription(ShortcutName + " · 双击直接打开工作室");
            string photo = Path.Combine(Path.GetDirectoryName(executable), "assets", "app-icon.ico");
            link.SetIconLocation(File.Exists(photo) ? photo : executable, 0);
            ((IPersistFile)link).Save(path, true);
        } finally {
            Marshal.FinalReleaseComObject(link);
        }
        if (!Matches(path, executable)) throw new IOException("Windows 未能保存可打开的桌面快捷方式：" + path);
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

    internal static int SelfTest(string root) {
        string fixture = Path.Combine(root, "work", "快捷方式 " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixture);
        try {
            string desktop = Path.Combine(fixture, "OneDrive", "桌面");
            string executable = Path.Combine(fixture, "中文 程序.exe");
            File.Copy(Assembly.GetExecutingAssembly().Location, executable);
            string path = Create(executable, desktop);
            if (!Matches(path, executable) || Path.GetDirectoryName(path) != desktop) return 20;
            if (Create(executable, desktop) != path || Directory.GetFiles(desktop, "*.lnk").Length != 1) return 21;
            string moved = Path.Combine(fixture, "移动后 程序.exe");
            File.Move(executable, moved);
            if (Create(moved, desktop) != path || !Matches(path, moved)) return 22;
            Console.WriteLine("Desktop link created and verified for a redirected Unicode path and repaired after a move.");
            return 0;
        } finally {
            Directory.Delete(fixture, true);
        }
    }
}
