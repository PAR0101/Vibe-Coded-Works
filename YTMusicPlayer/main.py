#!/usr/bin/env python3
import sys, os

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
os.chdir(_DIR)

print("Running from:", _DIR)
print("Files found:", os.listdir(_DIR))

def check_dependencies():
    missing = []
    try: import PyQt5
    except ImportError: missing.append("PyQt5")
    try: import yt_dlp
    except ImportError: missing.append("yt-dlp")
    try: import requests
    except ImportError: missing.append("requests")
    try: import sounddevice
    except ImportError: missing.append("sounddevice")
    try: import numpy
    except ImportError: missing.append("numpy")
    if missing:
        print("=" * 60)
        print("  Missing:", ", ".join(missing))
        print("  Run: pip install", " ".join(missing))
        print("=" * 60)
        sys.exit(1)

check_dependencies()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("YTMusicPlayer")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
