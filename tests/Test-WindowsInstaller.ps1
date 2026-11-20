param(
    [Parameter(Mandatory = $true)][string]$FfmpegArchive,
    [string]$FixtureRoot = (Join-Path ([IO.Path]::GetTempPath()) ('wang-installer-tests-' + [guid]::NewGuid().ToString('N').Substring(0, 8)))
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$archive = (Resolve-Path -LiteralPath $FfmpegArchive).Path
$pins = Get-Content -Raw -LiteralPath (Join-Path $repo 'windows/runtime-pins.json') | ConvertFrom-Json
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash -ne $pins.ffmpeg.sha256) {
    throw 'Test FFmpeg archive must match the installer pin.'
}
if (Test-Path -LiteralPath $FixtureRoot) { throw 'Use a new empty fixture path.' }
$binaries = New-Item -ItemType Directory -Path (Join-Path $FixtureRoot 'binaries') -Force
foreach ($name in @('Start Voice Studio.exe','WebView2Loader.dll','Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll')) {
    Copy-Item -LiteralPath (Join-Path $repo $name) -Destination $binaries.FullName
}
$support = New-Item -ItemType Directory -Path (Join-Path $binaries.FullName 'windows')
foreach ($name in @('runtime-pins.json','check_install.py')) {
    Copy-Item -LiteralPath (Join-Path $repo "windows/$name") -Destination $support.FullName
}
Get-ChildItem -LiteralPath $repo -Filter 'requirements-*.txt' -File | Copy-Item -Destination $binaries.FullName
$helper = Join-Path $binaries.FullName 'InstallerTests.exe'
& $compiler /nologo /codepage:65001 /target:exe /platform:x64 /reference:System.Windows.Forms.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll "/out:$helper" (Join-Path $PSScriptRoot 'Windows-Installer.Tests.cs')
if ($LASTEXITCODE -ne 0) { throw 'Windows installer tests failed to build' }
& $helper (Join-Path $binaries.FullName 'Start Voice Studio.exe') $archive (Join-Path $FixtureRoot 'fixtures')
if ($LASTEXITCODE -ne 0) { throw 'Windows installer regression test failed' }
