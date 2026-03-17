# YTMusicPlayer Launcher
Set-Location $PSScriptRoot

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  YTMusicPlayer - Starting..." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# Find python
$python = $null

# Check PATH first
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python") { $python = "python" }
} catch {}

# Check known ASUS/custom install path
if (-not $python) {
    $customPath = "C:\Users\ASUS\Documents\SCHOOL self PROJECTS\PYTHON INSTALL FOLDER\python.exe"
    if (Test-Path $customPath) {
        $python = $customPath
        Write-Host "Found Python at custom path." -ForegroundColor Green
    }
}

# Check common install locations
if (-not $python) {
    $locations = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe"
    )
    foreach ($loc in $locations) {
        if (Test-Path $loc) { $python = $loc; break }
    }
}

if (-not $python) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Install from https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
& $python -m pip install PyQt5 yt-dlp requests Pillow --quiet

Write-Host "Launching..." -ForegroundColor Green
& $python main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSomething went wrong." -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
