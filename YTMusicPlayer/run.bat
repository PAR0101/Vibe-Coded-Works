@echo off
cd /d "%~dp0"

echo =======================================
echo   YTMusicPlayer - Starting...
echo =======================================

:: ---- CHECK FFMPEG ----
if exist "%cd%\ffmpeg.exe" (
    echo FFmpeg found in folder.
    goto ffmpeg_done
)

where ffmpeg >nul 2>&1
if %errorlevel% == 0 (
    echo FFmpeg found in system PATH.
    goto ffmpeg_done
)

echo FFmpeg not found. Installing with Python...
python get_ffmpeg.py

:ffmpeg_done

:: ---- PYTHON CHECK ----
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Installing dependencies...
    python -m pip install PyQt5 yt-dlp requests Pillow sounddevice numpy --quiet
    echo Launching...
    python main.py
    goto end
)

py --version >nul 2>&1
if %errorlevel% == 0 (
    echo Installing dependencies...
    py -m pip install PyQt5 yt-dlp requests Pillow sounddevice numpy --quiet
    echo Launching...
    py main.py
    goto end
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON="%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto found
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON="%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & goto found
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PYTHON="%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & goto found

echo ERROR: Python not found. Install from https://python.org
pause & goto end

:found
%PYTHON% -m pip install PyQt5 yt-dlp requests Pillow sounddevice numpy --quiet
%PYTHON% main.py

:end
if %errorlevel% neq 0 ( echo. & echo Something went wrong. & pause )