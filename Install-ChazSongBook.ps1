<#
.SYNOPSIS
  Installs Chaz SongBook for the current user (no admin needed).

.DESCRIPTION
  Finds the app next to this script (an extracted "Chaz SongBook" folder, or the
  ChazSongBook-*-win64.zip), verifies SHA256 checksums, copies it to
  %LOCALAPPDATA%\Programs\Chaz SongBook, creates Start Menu + Desktop shortcuts,
  registers an uninstaller under Settings > Apps, and launches it.
  Your songs are NOT touched: they live in %APPDATA%\Chazmaniac\SongBook (or the
  folder you picked in File > Data folder).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\OneDrive\Apps\Chaz SongBook\Install-ChazSongBook.ps1"
#>
[CmdletBinding()]
param(
    [string]$Source,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Chaz SongBook'),
    [switch]$NoDesktopShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$AppName = 'Chaz SongBook'
$ExeName = 'ChazSongBook.exe'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }

function Say([string]$msg, [string]$color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Get-Sha256([string]$path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }

function Test-Sums([string]$baseDir) {
    $sumsFile = Join-Path $baseDir 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $sumsFile)) { throw "SHA256SUMS.txt not found in $baseDir" }
    $n = 0
    foreach ($line in Get-Content -LiteralPath $sumsFile) {
        if ($line -match '^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
            $expected = $Matches[1].ToLowerInvariant()
            $rel = $Matches[2] -replace '/', '\'
            $file = Join-Path $baseDir $rel
            if (-not (Test-Path -LiteralPath $file)) { throw "Missing file: $rel" }
            $actual = Get-Sha256 $file
            if ($actual -ne $expected) { throw "Checksum mismatch: $rel`n  expected $expected`n  actual   $actual" }
            $n++
        }
    }
    if ($n -eq 0) { throw 'SHA256SUMS.txt has no entries' }
    return $n
}

Say ''
Say "  CHAZ SONGBOOK  installer" 'Yellow'
Say "  ------------------------" 'DarkRed'

# ---------------------------------------------------------------- locate payload
$payloadRoot = $null
$tempDir = $null
$zip = $null
if ($Source) {
    $src = (Resolve-Path -LiteralPath $Source).Path
    if ((Get-Item -LiteralPath $src).PSIsContainer) { $payloadRoot = $src } else { $zip = Get-Item -LiteralPath $src }
} elseif (Test-Path -LiteralPath (Join-Path $here "$AppName\$ExeName")) {
    $payloadRoot = $here
} else {
    $zip = Get-ChildItem -LiteralPath $here -Filter 'ChazSongBook-*-win64.zip' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $zip) { throw "Couldn't find the '$AppName' folder or a ChazSongBook-*-win64.zip next to this script ($here)." }
}

if ($zip) {
    Say "Package : $($zip.FullName)"
    $zipHash = Get-Sha256 $zip.FullName
    $sidecar = "$($zip.FullName).sha256"
    if (Test-Path -LiteralPath $sidecar) {
        $expected = ((Get-Content -LiteralPath $sidecar -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
        if ($zipHash -ne $expected) { throw "ZIP checksum mismatch!`n  expected $expected`n  actual   $zipHash`nThe download may be incomplete (OneDrive still syncing?) - try again in a minute." }
        Say "SHA256  : $zipHash  (verified)" 'Green'
    } else {
        Say "SHA256  : $zipHash  (no .sha256 file to compare against - compare with the published value)" 'Yellow'
    }
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("ChazSongBook-install-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($zip.FullName, $tempDir)
    $payloadRoot = $tempDir
}

try {
    $appSrc = Join-Path $payloadRoot $AppName
    if (-not (Test-Path -LiteralPath (Join-Path $appSrc $ExeName))) { throw "$ExeName not found in $appSrc" }
    $count = Test-Sums $payloadRoot
    Say "Verified: $count files match SHA256SUMS.txt" 'Green'

    # ------------------------------------------------------------ stop old copy
    $running = Get-Process -Name 'ChazSongBook' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) }
    if ($running) {
        Say 'Closing the running Chaz SongBook (your work autosaves)...' 'Yellow'
        $running | ForEach-Object { [void]$_.CloseMainWindow() }
        Start-Sleep -Seconds 3
        $running | Where-Object { -not $_.HasExited } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }

    # ------------------------------------------------------------ copy
    Say "Install : $InstallDir"
    if (Test-Path -LiteralPath $InstallDir) {
        Get-ChildItem -LiteralPath $InstallDir -Force | Where-Object { $_.Name -ne 'Uninstall-ChazSongBook.ps1' } |
            Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
    Copy-Item -Path (Join-Path $appSrc '*') -Destination $InstallDir -Recurse -Force
    Get-ChildItem -LiteralPath $InstallDir -Recurse -File | Unblock-File -ErrorAction SilentlyContinue

    $exe = Join-Path $InstallDir $ExeName
    if ((Get-Sha256 $exe) -ne (Get-Sha256 (Join-Path $appSrc $ExeName))) { throw 'Installed exe does not match the package (copy failed?)' }
    Say 'Copied and re-verified.' 'Green'

    # ------------------------------------------------------------ uninstaller
    $uninst = Join-Path $InstallDir 'Uninstall-ChazSongBook.ps1'
    @'
$ErrorActionPreference = 'SilentlyContinue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-Process -Name 'ChazSongBook' | Stop-Process -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'Chaz SongBook.lnk') -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Chaz SongBook.lnk') -Force
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ChazSongBook' -Recurse -Force
Set-Location $env:TEMP
Remove-Item $dir -Recurse -Force
Write-Host 'Chaz SongBook removed. Your songs were kept in %APPDATA%\Chazmaniac\SongBook (or your chosen data folder).'
'@ | Set-Content -LiteralPath $uninst -Encoding UTF8

    $version = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
    $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ChazSongBook'
    New-Item -Path $key -Force | Out-Null
    $props = @{
        DisplayName = $AppName; DisplayVersion = "$version"; Publisher = 'Chazmaniac'
        DisplayIcon = $exe; InstallLocation = $InstallDir; NoModify = 1; NoRepair = 1
        UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninst`""
    }
    foreach ($k in $props.Keys) { New-ItemProperty -Path $key -Name $k -Value $props[$k] -Force | Out-Null }

    # ------------------------------------------------------------ shortcuts
    $shell = New-Object -ComObject WScript.Shell
    $targets = @(Join-Path ([Environment]::GetFolderPath('Programs')) "$AppName.lnk")
    if (-not $NoDesktopShortcut) { $targets += (Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk") }
    foreach ($lnkPath in $targets) {
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.TargetPath = $exe
        $lnk.WorkingDirectory = $InstallDir
        $lnk.IconLocation = "$exe,0"
        $lnk.Description = 'Capture song ideas: BPM/key, lyrics, arrangement'
        $lnk.Save()
        Say "Shortcut: $lnkPath" 'Green'
    }

    Say ''
    Say "Done! Chaz SongBook $version is installed." 'Yellow'
    Say "Your songs live in: $env:APPDATA\Chazmaniac\SongBook  (File > Data folder to move them to OneDrive)"
    if (-not $NoLaunch) { Start-Process -FilePath $exe -WorkingDirectory $InstallDir }
}
finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
}
