@echo off
cd /d "%~dp0"
echo =======================================
echo   YTMusicPlayer - Starting...
echo =======================================

if exist "%cd%\ffmpeg.exe" ( echo FFmpeg found. & goto ffmpeg_done )
where ffmpeg >nul 2>&1
if %errorlevel% == 0 ( echo FFmpeg in PATH. & goto ffmpeg_done )
echo FFmpeg not found. Installing...
python get_ffmpeg.py

:ffmpeg_done
python --version >nul 2>&1
if %errorlevel% == 0 (
    python -m pip install PyQt5 yt-dlp requests Pillow sounddevice numpy --quiet
    python main.py & goto end
)
py --version >nul 2>&1
if %errorlevel% == 0 (
    py -m pip install PyQt5 yt-dlp requests Pillow sounddevice numpy --quiet
    py main.py & goto end
)
echo ERROR: Python not found. Install from https://python.org
pause
:end
if %errorlevel% neq 0 ( echo. & echo Something went wrong. & pause )
