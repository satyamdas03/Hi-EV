#Requires -Version 5.1
<#
.SYNOPSIS
    Install Hi-EV locally on Windows without PyInstaller (avoids antivirus false-positives).

.DESCRIPTION
    - Checks Python 3.12+
    - Creates %LOCALAPPDATA%\Hi-EV venv
    - Installs Python dependencies and desktop extras
    - Builds the web frontend
    - Creates Start Menu + Desktop shortcuts
    - Launches the Hi-EV setup wizard / desktop entry point

.EXAMPLE
    .\scripts\install_windows.ps1
#>
param(
    [switch]$SkipFrontendBuild,
    [switch]$NoShortcuts,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

$AppName = "Hi-EV"
$AppDir = Join-Path $env:LOCALAPPDATA $AppName
$VenvDir = Join-Path $AppDir "venv"
$RepoDir = $PSScriptRoot | Split-Path -Parent
$WebDir = Join-Path $RepoDir "web"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-PythonVersion {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python is not installed or not on PATH. Install Python 3.12+ from https://python.org and re-run."
    }
    $verString = python --version 2>&1 | Select-String -Pattern "Python (\d+)\.(\d+)"
    if (-not $verString) {
        throw "Could not determine Python version."
    }
    $major = [int]$verString.Matches.Groups[1].Value
    $minor = [int]$verString.Matches.Groups[2].Value
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 12)) {
        throw "Python $major.$minor found, but Hi-EV requires Python 3.12+."
    }
    Write-Host "Python $major.$minor OK"
}

function Install-Dependencies {
    if (-not (Test-Path $VenvDir)) {
        Write-Step "Creating Python virtual environment at $VenvDir"
        python -m venv $VenvDir
    }

    $python = Join-Path $VenvDir "Scripts\python.exe"
    $pip = Join-Path $VenvDir "Scripts\pip.exe"

    Write-Step "Upgrading pip"
    & $python -m pip install --upgrade pip | Out-Null

    Write-Step "Installing Hi-EV Python dependencies (this may take a few minutes)"
    & $pip install -e $RepoDir | ForEach-Object { Write-Host $_ }
    Write-Step "Installing desktop extras (pynput, pystray, pyinstaller)"
    & $pip install pynput pystray pyinstaller | ForEach-Object { Write-Host $_ }
}

function Build-Frontend {
    if ($SkipFrontendBuild) {
        Write-Step "Skipping frontend build"
        return
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-Warning "npm not found. Skipping frontend build. Install Node.js from https://nodejs.org and re-run with -SkipFrontendBuild:`$false."
        return
    }

    Write-Step "Building Hi-EV web frontend"
    Push-Location $WebDir
    try {
        npm install | ForEach-Object { Write-Host $_ }
        npm run build | ForEach-Object { Write-Host $_ }
    } finally {
        Pop-Location
    }
}

function New-Shortcut {
    param(
        [string]$TargetPath,
        [string]$ShortcutPath,
        [string]$IconPath = "",
        [string]$Arguments = ""
    )
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    if ($Arguments) { $Shortcut.Arguments = $Arguments }
    if ($IconPath -and (Test-Path $IconPath)) { $Shortcut.IconLocation = $IconPath }
    $Shortcut.WorkingDirectory = $RepoDir
    $Shortcut.Save()
}

function Install-Shortcuts {
    if ($NoShortcuts) { return }

    Write-Step "Creating shortcuts"

    $pythonExe = Join-Path $VenvDir "Scripts\pythonw.exe"
    $desktopPresence = Join-Path $RepoDir "scripts\desktop_presence.py"

    $StartMenu = [Environment]::GetFolderPath("StartMenu")
    $ProgramsDir = Join-Path $StartMenu "Programs\$AppName"
    if (-not (Test-Path $ProgramsDir)) {
        New-Item -ItemType Directory -Path $ProgramsDir -Force | Out-Null
    }

    # Start Menu shortcut
    New-Shortcut `
        -TargetPath $pythonExe `
        -ShortcutPath (Join-Path $ProgramsDir "$AppName.lnk") `
        -Arguments "`"$desktopPresence`"" `

    # Desktop shortcut
    $DesktopDir = [Environment]::GetFolderPath("Desktop")
    New-Shortcut `
        -TargetPath $pythonExe `
        -ShortcutPath (Join-Path $DesktopDir "$AppName.lnk") `
        -Arguments "`"$desktopPresence`"" `

    Write-Host "Shortcuts created:" -ForegroundColor Green
    Write-Host "  Start Menu -> $ProgramsDir\$AppName.lnk"
    Write-Host "  Desktop    -> $DesktopDir\$AppName.lnk"
}

function Start-HiEV {
    if (-not $Launch) { return }

    Write-Step "Launching Hi-EV"
    $pythonExe = Join-Path $VenvDir "Scripts\pythonw.exe"
    $desktopPresence = Join-Path $RepoDir "scripts\desktop_presence.py"
    Start-Process -FilePath $pythonExe -ArgumentList "`"$desktopPresence`"" -WorkingDirectory $RepoDir
}

function Main {
    Write-Host "Hi-EV Windows Installer" -ForegroundColor Cyan
    Write-Host "Install directory: $AppDir"

    Test-PythonVersion
    Install-Dependencies
    Build-Frontend
    Install-Shortcuts
    Start-HiEV

    Write-Host "`nHi-EV is installed and ready." -ForegroundColor Green
    Write-Host "Run from source: $VenvDir\Scripts\pythonw.exe $RepoDir\scripts\desktop_presence.py"
}

Main
