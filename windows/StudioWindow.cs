// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.Diagnostics;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class StudioWindow : Form {
    private readonly Uri home;
    private readonly string profile;
    private readonly Action<string> log;
    private readonly WebView2 view = new WebView2 { Dock = DockStyle.Fill, Visible = false };
    private readonly Label message = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter };
    internal bool Ready { get; private set; }

    internal StudioWindow(string name, Icon icon, string url, string profile, Action<string> log) {
        home = new Uri(url);
        this.profile = profile;
        this.log = log;
        Text = name;
        Icon = icon;
        AutoScaleMode = AutoScaleMode.Dpi;
        StartPosition = FormStartPosition.CenterScreen;
        var screen = Screen.FromPoint(Cursor.Position).WorkingArea;
        Size = new Size(Math.Min(1280, screen.Width), Math.Min(880, screen.Height));
        MinimumSize = new Size(520, 420);
        BackColor = Color.FromArgb(22, 24, 30);
        message.ForeColor = Color.WhiteSmoke;
        message.Font = new Font("Microsoft YaHei UI", 13);
        message.Text = "正在打开工作室…";
        Controls.Add(view);
        Controls.Add(message);
        Shown += async (sender, args) => await Initialize();
    }

    internal void BringToUser() {
        if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
        Activate();
    }

    private async Task Initialize() {
        try {
            var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: profile);
            if (IsDisposed) return;
            await view.EnsureCoreWebView2Async(environment);
            if (IsDisposed) return;

            CoreWebView2 core = view.CoreWebView2;
            core.Settings.AreHostObjectsAllowed = false;
            core.Settings.IsWebMessageEnabled = false;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.IsStatusBarEnabled = false;
            core.NavigationStarting += (sender, e) => {
                if (IsLocal(e.Uri)) return;
                e.Cancel = true;
                if (e.IsUserInitiated) OpenExternal(e.Uri);
            };
            core.NewWindowRequested += (sender, e) => {
                e.Handled = true;
                if (!e.IsUserInitiated) return;
                if (IsLocal(e.Uri)) core.Navigate(e.Uri);
                else OpenExternal(e.Uri);
            };
            core.NavigationCompleted += (sender, e) => {
                if (!e.IsSuccess) {
                    message.Text = "工作室界面未能加载。请关闭窗口后重新打开。";
                    log("工作室窗口加载失败：" + e.WebErrorStatus);
                    return;
                }
                Ready = true;
                message.Visible = false;
                view.Visible = true;
                view.Focus();
                log("工作室 Windows 窗口已载入。");
            };
            core.Navigate(home.AbsoluteUri);
        } catch (Exception error) {
            if (IsDisposed) return;
            message.Text = error is WebView2RuntimeNotFoundException
                ? "这台电脑缺少 Microsoft WebView2 Runtime。\r\n安装 Windows WebView2 Runtime 后，重新打开工作室。"
                : "工作室窗口启动失败。\r\n" + error.Message;
            log(error.ToString());
        }
    }

    private bool IsLocal(string url) {
        Uri target;
        return Uri.TryCreate(url, UriKind.Absolute, out target) &&
               target.GetLeftPart(UriPartial.Authority) == home.GetLeftPart(UriPartial.Authority);
    }

    private void OpenExternal(string url) {
        Uri target;
        if (!Uri.TryCreate(url, UriKind.Absolute, out target) || target.Scheme != Uri.UriSchemeHttps) return;
        try {
            Process.Start(new ProcessStartInfo(target.AbsoluteUri) { UseShellExecute = true });
        } catch (Exception error) {
            log("无法打开链接：" + error.Message);
        }
    }
}

