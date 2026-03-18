#!/usr/bin/env python3
"""
setup_and_run.py — One-shot setup + launch script.
"""
import sys, subprocess, os

REQUIRED = ["PyQt5", "yt-dlp", "requests", "Pillow", "sounddevice", "numpy"]

def install_missing():
    missing = []
    for pkg in REQUIRED:
        name = {"PyQt5":"PyQt5","yt-dlp":"yt_dlp","Pillow":"PIL"}.get(pkg, pkg.replace("-","_").lower())
        try: __import__(name)
        except ImportError: missing.append(pkg)
    if missing:
        print(f"Installing: {', '.join(missing)} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + missing)
        print("Done.\n")

def main():
    print("=" * 56)
    print("  YTMusicPlayer — Setup & Launch")
    print("=" * 56)
    install_missing()
    script = os.path.join(os.path.dirname(__file__), "main.py")
    os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])

if __name__ == "__main__":
    main()
