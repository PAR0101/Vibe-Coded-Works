#!/usr/bin/env python3
"""
setup_and_run.py
────────────────
One-shot setup + launch script.
Run this instead of main.py the first time to auto-install dependencies.

    python setup_and_run.py
"""

import sys
import subprocess
import os


REQUIRED = ["PyQt5", "yt-dlp", "requests", "Pillow"]


def install_missing():
    missing = []
    for pkg in REQUIRED:
        import_name = pkg.replace("-", "_").lower()
        # special cases
        if pkg == "PyQt5":
            import_name = "PyQt5"
        elif pkg == "yt-dlp":
            import_name = "yt_dlp"
        elif pkg == "Pillow":
            import_name = "PIL"
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"Installing: {', '.join(missing)} …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade"] + missing
        )
        print("Done.\n")


def main():
    print("=" * 56)
    print("  YTMusicPlayer — Setup & Launch")
    print("=" * 56)
    install_missing()

    # Launch the app
    script = os.path.join(os.path.dirname(__file__), "main.py")
    os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])


if __name__ == "__main__":
    main()
