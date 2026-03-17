"""
get_ffmpeg.py
─────────────
Downloads a static ffmpeg.exe build directly into the YTMusicPlayer folder.
Run this once if you don't have ffmpeg installed.

    python get_ffmpeg.py
"""
import urllib.request
import zipfile
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "ffmpeg.exe")

URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)

def download_ffmpeg():
    if os.path.exists(DEST):
        print(f"ffmpeg already exists at: {DEST}")
        return

    print("Downloading ffmpeg (~75 MB)...")
    zip_path = os.path.join(HERE, "_ffmpeg_tmp.zip")

    def progress(count, block, total):
        pct = int(count * block * 100 / total)
        print(f"\r  {pct}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(URL, zip_path, progress)
        print("\nExtracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/bin/ffmpeg.exe"):
                    data = zf.read(name)
                    with open(DEST, "wb") as f:
                        f.write(data)
                    print(f"ffmpeg.exe saved to: {DEST}")
                    break
            else:
                print("ERROR: ffmpeg.exe not found inside zip")
                sys.exit(1)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    print("\nDone! You can now run: python main.py")

if __name__ == "__main__":
    download_ffmpeg()
