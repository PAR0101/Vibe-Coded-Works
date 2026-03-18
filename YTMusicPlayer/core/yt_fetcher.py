"""
core/yt_fetcher.py
──────────────────
Thin wrapper around yt-dlp for playlist / channel / URL extraction.
All heavy work runs in daemon threads — results returned via callbacks.
"""

import threading
from typing import Callable, Optional
import yt_dlp


_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    },
}


class YTFetcher:
    def __init__(self, cookie_file: Optional[str] = None):
        self.cookie_file = cookie_file

    def _opts(self, flat: bool = True) -> dict:
        opts = dict(_BASE_OPTS)
        opts["extract_flat"] = flat
        if self.cookie_file:
            opts["cookiefile"] = self.cookie_file
        return opts

    def fetch_url(self, url: str, callback: Callable, flat: bool = True):
        threading.Thread(
            target=self._fetch_worker, args=(url, callback, flat), daemon=True,
        ).start()

    def _fetch_worker(self, url: str, callback: Callable, flat: bool):
        try:
            with yt_dlp.YoutubeDL(self._opts(flat)) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = info.get("entries") if info else None
            if entries is not None: callback(list(entries))
            elif info: callback([info])
            else: callback([])
        except Exception:
            callback([])

    def fetch_playlist(self, playlist_url: str, callback: Callable):
        self.fetch_url(playlist_url, callback, flat=True)

    def fetch_liked_videos(self, callback: Callable):
        self.fetch_url("https://www.youtube.com/playlist?list=LL", callback, flat=True)

    def fetch_history(self, callback: Callable):
        self.fetch_url("https://www.youtube.com/feed/history", callback, flat=True)

    def fetch_recommendations(self, callback: Callable):
        self.fetch_url("https://www.youtube.com", callback, flat=True)

    def search(self, query: str, max_results: int, callback: Callable):
        def worker():
            try:
                opts = self._opts(flat=True)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                callback(list(info.get("entries") or []))
            except Exception:
                callback([])
        threading.Thread(target=worker, daemon=True).start()
