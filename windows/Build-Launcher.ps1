param([string]$WebViewPackage)
$ErrorActionPreference = 'Stop'
$appDirectory = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'The .NET Framework C# compiler was not found.' }
$sdkVersion = '1.0.4314.35'
$sdkSha = '90778DEB1B77E36292828B4B5833C9255C27533F40E0DDD55891AE718944EDC4'
$downloaded = -not $WebViewPackage
if ($downloaded) {
    $WebViewPackage = Join-Path ([IO.Path]::GetTempPath()) ("studio-webview2-" + [guid]::NewGuid() + ".nupkg")
}
try {
    if ($downloaded) {
        $id = 'microsoft.web.webview2'
        $url = "https://api.nuget.org/v3-flatcontainer/$id/$sdkVersion/$id.$sdkVersion.nupkg"
        Invoke-WebRequest -Uri $url -OutFile $WebViewPackage -TimeoutSec 60
    }
    if ((Get-FileHash -LiteralPath $WebViewPackage -Algorithm SHA256).Hash -ne $sdkSha) {
        throw 'WebView2 SDK checksum mismatch.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $WebViewPackage))
    $licenses = Join-Path $PSScriptRoot 'webview2'
    New-Item -ItemType Directory -Force -Path $licenses | Out-Null
    $sdkFiles = @{
        'lib/net462/Microsoft.Web.WebView2.Core.dll' = $appDirectory
        'lib/net462/Microsoft.Web.WebView2.WinForms.dll' = $appDirectory
        'runtimes/win-x64/native/WebView2Loader.dll' = $appDirectory
        'LICENSE.txt' = $licenses
        'NOTICE.txt' = $licenses
    }
    try {
        foreach ($source in $sdkFiles.Keys) {
            $entry = $archive.GetEntry($source)
            if (-not $entry) { throw "Missing WebView2 SDK entry $source." }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $sdkFiles[$source] $entry.Name), $true)
        }
    } finally {
        $archive.Dispose()
    }
} finally {
    if ($downloaded -and (Test-Path -LiteralPath $WebViewPackage)) {
        Remove-Item -LiteralPath $WebViewPackage
    }
}
$compileArguments = @(
    ('/reference:' + (Join-Path $appDirectory 'Microsoft.Web.WebView2.Core.dll')),
    ('/reference:' + (Join-Path $appDirectory 'Microsoft.Web.WebView2.WinForms.dll')),
    '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    '/reference:System.Net.Http.dll', '/reference:System.IO.Compression.dll',
    '/reference:System.IO.Compression.FileSystem.dll', '/reference:System.Windows.Forms.dll',
    '/reference:System.Drawing.dll', '/reference:System.Web.Extensions.dll',
    ('/win32icon:' + (Join-Path $appDirectory 'assets\app-icon.ico')),
    ('/win32manifest:' + (Join-Path $PSScriptRoot 'launcher.manifest')),
    ('/out:' + (Join-Path $appDirectory 'Start Voice Studio.exe')),
    (Join-Path $PSScriptRoot 'VoiceStudioLauncher.cs'),
    (Join-Path $PSScriptRoot 'StudioWindow.cs'),
    (Join-Path $PSScriptRoot 'DesktopIntegration.cs')
)
& $compiler @compileArguments
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
Write-Output 'Built Start Voice Studio.exe'
