// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

internal static class DesktopIntegration {
    internal const string ShortcutName = "王洪文语音工作室";
    private static object Get(object value, string property) {
        return value.GetType().InvokeMember(property, BindingFlags.GetProperty, null, value, null);
    }
    private static void Set(object value, string property, object data) {
        value.GetType().InvokeMember(property, BindingFlags.SetProperty, null, value, new[] {data});
    }
    private static void Release(object value) {
        if (value != null && Marshal.IsComObject(value)) Marshal.FinalReleaseComObject(value);
    }
    internal static string Create(string executable, string desktop) {
        executable = Path.GetFullPath(executable);
        if (!File.Exists(executable)) throw new FileNotFoundException("找不到启动程序，请先完整解压安装包。", executable);
        if (String.IsNullOrWhiteSpace(desktop)) throw new IOException("无法找到当前用户的桌面文件夹。");
        Directory.CreateDirectory(desktop);
        string path = Path.Combine(desktop, ShortcutName + ".lnk");
        object shell = null, link = null;
        try {
            shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
            link = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] {path});
            Set(link, "TargetPath", executable);
            Set(link, "Arguments", "--open");
            Set(link, "WorkingDirectory", Path.GetDirectoryName(executable));
            Set(link, "Description", ShortcutName + " · 双击直接打开工作室");
            string photoIcon = Path.Combine(Path.GetDirectoryName(executable), "assets", "app-icon.ico");
            Set(link, "IconLocation", (File.Exists(photoIcon) ? photoIcon : executable) + ",0");
            link.GetType().InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
        } finally { Release(link); Release(shell); }
        return path;
    }
    internal static string CreateForCurrentUser() {
        return Create(Assembly.GetExecutingAssembly().Location, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));
    }
    internal static string InstanceKey(string root) {
        using (var sha = SHA256.Create()) return "Local\\VoiceStudio-" + BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(root).TrimEnd('\\').ToUpperInvariant()))).Replace("-", "");
    }
    internal static int SelfTest(string root) {
        string fixture = Path.Combine(root, "work", "桌面快捷方式测试 " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixture);
        object shell = null, link = null;
        try {
            string executable = Path.Combine(fixture, "中文 程序.exe");
            File.WriteAllText(executable, "test");
            string path = Create(executable, fixture);
            // Recreating the same entry repairs a shortcut after an app-folder move.
            string moved = Path.Combine(fixture, "移动后 程序.exe"); File.WriteAllText(moved, "test");
            if (Create(moved, fixture) != path) return 20;
            shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
            link = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] {path});
            if (!String.Equals((string)Get(link, "TargetPath"), moved, StringComparison.OrdinalIgnoreCase)) return 21;
            if ((string)Get(link, "Arguments") != "--open" || (string)Get(link, "WorkingDirectory") != fixture) return 22;
            Console.WriteLine("Desktop shortcut creation, Chinese/spaced paths, direct-open arguments and moved-folder repair passed.");
            return 0;
        } finally { Release(link); Release(shell); Directory.Delete(fixture, true); }
    }
}
