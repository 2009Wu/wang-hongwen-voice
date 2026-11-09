$ErrorActionPreference = 'Stop'
$appDirectory = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'The .NET Framework C# compiler was not found.' }
$compileArguments = @(
    '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    '/reference:System.Net.Http.dll', '/reference:System.IO.Compression.dll',
    '/reference:System.IO.Compression.FileSystem.dll', '/reference:System.Windows.Forms.dll',
    '/reference:System.Drawing.dll', '/reference:System.Web.Extensions.dll',
    ('/win32icon:' + (Join-Path $appDirectory 'assets\app-icon.ico')),
    ('/win32manifest:' + (Join-Path $PSScriptRoot 'launcher.manifest')),
    ('/out:' + (Join-Path $appDirectory 'Start Voice Studio.exe')),
    (Join-Path $PSScriptRoot 'VoiceStudioLauncher.cs'),
    (Join-Path $PSScriptRoot 'DesktopIntegration.cs')
)
& $compiler @compileArguments
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
Write-Output 'Built Start Voice Studio.exe'
