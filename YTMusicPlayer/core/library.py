"""
core/library.py
───────────────
Manages the local library: playlists, liked songs, history, and
a disk-based thumbnail/metadata cache for fast replay.
"""

import json
import os
import time
import hashlib
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal


DATA_DIR       = os.path.join(os.path.expanduser("~"), ".ytmusicplayer")
PLAYLISTS_FILE = os.path.join(DATA_DIR, "playlists.json")
HISTORY_FILE   = os.path.join(DATA_DIR, "history.json")
LIKED_FILE     = os.path.join(DATA_DIR, "liked.json")
CACHE_DIR      = os.path.join(DATA_DIR, "cache")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def _load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Library(QObject):
    library_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._playlists: dict = _load_json(PLAYLISTS_FILE, {})
        self._history:   list = _load_json(HISTORY_FILE,   [])
        self._liked:     dict = _load_json(LIKED_FILE,     {})

    def add_to_history(self, track_dict: dict):
        self._history = [e for e in self._history if e.get("id") != track_dict.get("id")]
        self._history.insert(0, {**track_dict, "_played_at": time.time()})
        self._history = self._history[:200]
        _save_json(HISTORY_FILE, self._history)
        self.library_changed.emit()

    def get_history(self) -> list:
        return list(self._history)

    def clear_history(self):
        self._history = []
        _save_json(HISTORY_FILE, self._history)
        self.library_changed.emit()

    def like_track(self, track_dict: dict):
        vid = track_dict.get("id", "")
        if vid:
            self._liked[vid] = {**track_dict, "_liked_at": time.time()}
            _save_json(LIKED_FILE, self._liked)
            self.library_changed.emit()

    def unlike_track(self, video_id: str):
        if video_id in self._liked:
            del self._liked[video_id]
            _save_json(LIKED_FILE, self._liked)
            self.library_changed.emit()

    def is_liked(self, video_id: str) -> bool:
        return video_id in self._liked

    def get_liked(self) -> list:
        return sorted(self._liked.values(), key=lambda x: x.get("_liked_at",0), reverse=True)

    def create_playlist(self, name: str) -> str:
        pid = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:8]
        self._playlists[pid] = {"name": name, "tracks": [], "created": time.time()}
        _save_json(PLAYLISTS_FILE, self._playlists)
        self.library_changed.emit()
        return pid

    def rename_playlist(self, pid: str, new_name: str):
        if pid in self._playlists:
            self._playlists[pid]["name"] = new_name
            _save_json(PLAYLISTS_FILE, self._playlists)
            self.library_changed.emit()

    def delete_playlist(self, pid: str):
        self._playlists.pop(pid, None)
        _save_json(PLAYLISTS_FILE, self._playlists)
        self.library_changed.emit()

    def add_to_playlist(self, pid: str, track_dict: dict):
        if pid in self._playlists:
            tracks = self._playlists[pid]["tracks"]
            if not any(t.get("id") == track_dict.get("id") for t in tracks):
                tracks.append(track_dict)
                _save_json(PLAYLISTS_FILE, self._playlists)
                self.library_changed.emit()

    def remove_from_playlist(self, pid: str, video_id: str):
        if pid in self._playlists:
            self._playlists[pid]["tracks"] = [
                t for t in self._playlists[pid]["tracks"] if t.get("id") != video_id
            ]
            _save_json(PLAYLISTS_FILE, self._playlists)
            self.library_changed.emit()

    def get_playlists(self) -> dict:
        return dict(self._playlists)

    def get_playlist_tracks(self, pid: str) -> list:
        return list(self._playlists.get(pid, {}).get("tracks", []))

    def cache_path(self, url: str) -> str:
        h = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{h}.jpg")

    def is_cached(self, url: str) -> bool:
        return os.path.exists(self.cache_path(url))

    def save_thumbnail(self, url: str, data: bytes):
        with open(self.cache_path(url), "wb") as f:
            f.write(data)
