"""
core/audio_engine.py  ─  v3
────────────────────────────
Fixes in this version
─────────────────────
* Seeking  – FfmpegPlayer accepts seek_ms and injects  -ss <seconds>  BEFORE
  -i in the ffmpeg command, so audio actually jumps to the chosen position
  instead of restarting from zero.
* Stream-URL caching  – seek() reuses the already-resolved URL when it is
  less than 5 minutes old, eliminating the ~3 s yt-dlp round-trip on seek.
"""

import threading
import time
import os
import subprocess
import shutil
from typing import Optional, Callable

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
import yt_dlp


# ── Locate ffmpeg ─────────────────────────────────────────────────────────────
def _find_ffmpeg() -> Optional[str]:
    here  = os.path.dirname(os.path.abspath(__file__))
    root  = os.path.dirname(here)
    paths = [
        shutil.which("ffmpeg"),
        os.path.join(root, "ffmpeg.exe"),
        os.path.join(root, "ffmpeg"),
        os.path.join(here, "ffmpeg.exe"),
        os.path.join(here, "ffmpeg"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


FFMPEG = _find_ffmpeg()
print(f"[AudioEngine] ffmpeg: {FFMPEG or 'NOT FOUND'}")

try:
    import sounddevice as sd
    sd.query_devices(kind="output")
    _SD_OK = True
    print("[AudioEngine] sounddevice OK")
except Exception as _e:
    _SD_OK = False
    print(f"[AudioEngine] sounddevice error: {_e}")


SAMPLE_RATE       = 44100
CHANNELS          = 2
BYTES_PER_SAMPLE  = 2
BYTES_PER_FRAME   = CHANNELS * BYTES_PER_SAMPLE
CHUNK_SIZE        = SAMPLE_RATE // 10 * BYTES_PER_FRAME   # 100 ms

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")

YDL_OPTS_SEARCH = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "noplaylist": False,
    "skip_download": True,
    "http_headers": {"User-Agent": _UA},
}

YDL_OPTS_STREAM = {
    **YDL_OPTS_SEARCH,
    "extract_flat": False,
    "noplaylist": True,
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
}

_URL_CACHE_TTL = 300   # seconds before stream URL is considered stale


class TrackInfo:
    def __init__(self, data: dict):
        self.id          = data.get("id", "")
        self.title       = data.get("title", "Unknown")
        self.channel     = data.get("uploader") or data.get("channel", "Unknown")
        self.duration    = int(data.get("duration") or 0)
        self.thumbnail   = data.get("thumbnail", "")
        self.webpage_url = data.get("webpage_url", f"https://youtu.be/{self.id}")
        self.stream_url  = data.get("url", "")
        self._url_time   = 0.0   # epoch when stream_url was last resolved

    @property
    def duration_str(self):
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def __repr__(self):
        return f"<TrackInfo '{self.title}'>"


class FfmpegPlayer:
    """
    Streams audio URL → ffmpeg → sounddevice in a daemon thread.
    seek_ms  – start ffmpeg with  -ss <seek_seconds>  placed BEFORE  -i,
               giving fast keyframe-accurate seeking without decoding from start.
    """

    def __init__(self, url: str, seek_ms: int = 0, volume: float = 0.7,
                 on_position: Callable = None,
                 on_end:      Callable = None,
                 on_error:    Callable = None):
        self._url       = url
        self._seek_ms   = max(0, seek_ms)
        self._volume    = max(0.0, min(2.0, volume))
        self._on_pos    = on_position
        self._on_end    = on_end
        self._on_error  = on_error
        self._proc      = None
        self._thread    = None
        self._stop_evt  = threading.Event()
        self._pause_evt = threading.Event()
        self._pos_ms    = self._seek_ms    # counter starts at seek point
        self._lock      = threading.Lock()

    def start(self):
        self._stop_evt.clear()
        self._pause_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            cmd = [FFMPEG, "-loglevel", "quiet"]

            # -ss before -i  →  fast seek using keyframes (no full decode)
            seek_s = self._seek_ms / 1000.0
            if seek_s > 0.0:
                cmd += ["-ss", f"{seek_s:.3f}"]

            cmd += [
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-headers", f"User-Agent: {_UA}\r\n",
                "-i", self._url,
                "-vn",
                "-f", "s16le",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "pipe:1",
            ]

            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
            )

            with sd.RawOutputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS,
                dtype="int16", blocksize=SAMPLE_RATE // 10,
            ) as stream:
                while not self._stop_evt.is_set():
                    if self._pause_evt.is_set():
                        time.sleep(0.05)
                        continue
                    data = self._proc.stdout.read(CHUNK_SIZE)
                    if not data:
                        break
                    if self._volume != 1.0:
                        arr  = np.frombuffer(data, dtype=np.int16).copy()
                        arr  = (arr * self._volume).clip(-32768, 32767).astype(np.int16)
                        data = arr.tobytes()
                    stream.write(data)
                    frames = len(data) / BYTES_PER_FRAME
                    with self._lock:
                        self._pos_ms += int(frames / SAMPLE_RATE * 1000)
                    if self._on_pos:
                        self._on_pos(self._pos_ms)

            if self._proc:
                self._proc.wait()
            if not self._stop_evt.is_set() and self._on_end:
                self._on_end()

        except Exception as exc:
            if not self._stop_evt.is_set() and self._on_error:
                self._on_error(str(exc))

    def pause(self):  self._pause_evt.set()
    def resume(self): self._pause_evt.clear()

    def stop(self):
        self._stop_evt.set()
        if self._proc:
            try: self._proc.kill()
            except Exception: pass

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(2.0, vol))

    @property
    def position_ms(self):
        with self._lock: return self._pos_ms

    @property
    def is_paused(self):
        return self._pause_evt.is_set()


class AudioEngine(QObject):
    track_changed          = pyqtSignal(object)
    state_changed          = pyqtSignal(str)
    position_changed       = pyqtSignal(int)
    duration_changed       = pyqtSignal(int)
    volume_changed         = pyqtSignal(int)
    error_occurred         = pyqtSignal(str)
    search_results_ready   = pyqtSignal(list)
    queue_ended            = pyqtSignal(object)     # last TrackInfo
    smart_autoplay_results = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_track: Optional[TrackInfo] = None
        self._queue        = []
        self._queue_index  = -1
        self._cookie_file  = None
        self._volume       = 70
        self._state        = "stopped"
        self._pos_ms       = 0
        self._dur_ms       = 0
        self._loading      = False
        self._looping      = False
        self._player: Optional[FfmpegPlayer] = None

        self._poll = QTimer(self)
        self._poll.setInterval(500)
        self._poll.timeout.connect(self._on_poll)
        self._poll.start()

        if not FFMPEG:  print("[AudioEngine] WARNING: ffmpeg not found. Run get_ffmpeg.py.")
        if not _SD_OK:  print("[AudioEngine] WARNING: sounddevice not working.")

    # ── Public API ────────────────────────────────────────────────────────────

    def set_cookie_file(self, path: str):
        self._cookie_file = path

    def search(self, query: str, max_results: int = 20):
        threading.Thread(target=self._search_worker,
                         args=(query, max_results, False), daemon=True).start()

    def search_similar(self, track: TrackInfo, max_results: int = 15):
        query = f"{track.title} {track.channel} similar mix"
        threading.Thread(target=self._search_worker,
                         args=(query, max_results, True), daemon=True).start()

    def load_and_play(self, track: TrackInfo):
        if self._loading: return
        self._stop_player()
        self._current_track = track
        self._state = "loading"
        self._pos_ms = 0
        self.state_changed.emit("loading")
        self.track_changed.emit(track)
        threading.Thread(target=self._resolve_worker, args=(track, 0), daemon=True).start()

    def set_queue(self, tracks: list, start_index: int = 0):
        self._queue = list(tracks)
        self._queue_index = start_index
        if self._queue:
            self.load_and_play(self._queue[self._queue_index])

    def append_to_queue(self, track: TrackInfo):
        self._queue.append(track)

    def extend_queue(self, tracks: list):
        self._queue.extend(tracks)

    def next_track(self):
        if self._queue_index < len(self._queue) - 1:
            self._queue_index += 1
            self.load_and_play(self._queue[self._queue_index])

    def previous_track(self):
        if self._pos_ms > 3000:
            self._restart_current()
        elif self._queue_index > 0:
            self._queue_index -= 1
            self.load_and_play(self._queue[self._queue_index])

    def play(self):
        if self._state == "paused" and self._player:
            self._player.resume(); self._state = "playing"; self.state_changed.emit("playing")

    def pause(self):
        if self._state == "playing" and self._player:
            self._player.pause(); self._state = "paused"; self.state_changed.emit("paused")

    def toggle_play_pause(self):
        if   self._state == "playing": self.pause()
        elif self._state == "paused":  self.play()

    def stop(self):
        self._stop_player()
        self._state = "stopped"; self._pos_ms = 0
        self.state_changed.emit("stopped"); self.position_changed.emit(0)

    def seek(self, ms: int):
        """
        Jump to `ms` milliseconds.  Uses the cached stream URL when fresh
        (avoids a costly yt-dlp round-trip) and passes the seek offset to
        FfmpegPlayer so ffmpeg starts at the right position.
        """
        track = self._current_track
        if not track: return
        self._stop_player()
        self._pos_ms = ms

        url_age = time.time() - getattr(track, "_url_time", 0.0)
        if track.stream_url and url_age < _URL_CACHE_TTL:
            # Fast path — cached URL still valid
            self._pending_url  = track.stream_url
            self._pending_dur  = track.duration
            self._pending_seek = ms
            self._loading = False
            self._qt_play()
        else:
            threading.Thread(target=self._resolve_worker,
                             args=(track, ms), daemon=True).start()

    def set_volume(self, level: int):
        self._volume = max(0, min(100, level))
        if self._player: self._player.set_volume(self._volume / 100.0)
        self.volume_changed.emit(self._volume)

    def set_loop(self, on: bool):
        self._looping = on

    @property
    def volume(self):        return self._volume
    @property
    def position(self):      return self._pos_ms
    @property
    def duration(self):      return self._dur_ms
    @property
    def is_playing(self):    return self._state == "playing"
    @property
    def current_track(self): return self._current_track
    @property
    def queue(self):         return list(self._queue)
    @property
    def queue_index(self):   return self._queue_index

    # ── Internal ──────────────────────────────────────────────────────────────

    def _stop_player(self):
        if self._player: self._player.stop(); self._player = None

    def _restart_current(self):
        if self._current_track:
            self._stop_player(); self._pos_ms = 0
            threading.Thread(target=self._resolve_worker,
                             args=(self._current_track, 0), daemon=True).start()

    def _search_worker(self, query: str, max_results: int, is_autoplay: bool):
        try:
            opts = dict(YDL_OPTS_SEARCH)
            if self._cookie_file: opts["cookiefile"] = self._cookie_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = [TrackInfo(e) for e in (info.get("entries") or []) if e]
            (self.smart_autoplay_results if is_autoplay else self.search_results_ready).emit(results)
        except Exception as exc:
            self.error_occurred.emit(f"Search error: {exc}")
            (self.smart_autoplay_results if is_autoplay else self.search_results_ready).emit([])

    def _resolve_worker(self, track: TrackInfo, seek_ms: int = 0):
        self._loading = True
        try:
            opts = dict(YDL_OPTS_STREAM)
            if self._cookie_file: opts["cookiefile"] = self._cookie_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(track.webpage_url, download=False)

            track.stream_url = info.get("url", "")
            track.duration   = int(info.get("duration") or 0)
            track._url_time  = time.time()                      # stamp the cache
            if not track.thumbnail and info.get("thumbnail"):
                track.thumbnail = info["thumbnail"]

            self._pending_url  = track.stream_url
            self._pending_dur  = track.duration
            self._pending_seek = seek_ms

            from PyQt5.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_qt_play", _Qt.QueuedConnection)

        except Exception as exc:
            self._loading = False
            self.error_occurred.emit(f"Resolve error: {exc}")
            self.state_changed.emit("error")

    @pyqtSlot()
    def _qt_play(self):
        url      = getattr(self, "_pending_url",  "")
        duration = getattr(self, "_pending_dur",  0)
        seek_ms  = getattr(self, "_pending_seek", 0)
        self._loading = False

        if not url:
            self.error_occurred.emit("Could not get stream URL."); self.state_changed.emit("error"); return
        if not FFMPEG:
            self.error_occurred.emit("ffmpeg not found.  Run: python get_ffmpeg.py"); self.state_changed.emit("error"); return
        if not _SD_OK:
            self.error_occurred.emit("sounddevice not working.  pip install sounddevice"); self.state_changed.emit("error"); return

        self._dur_ms = duration * 1000
        self.duration_changed.emit(self._dur_ms)

        player = FfmpegPlayer(
            url, seek_ms=seek_ms, volume=self._volume / 100.0,
            on_position=self._cb_position, on_end=self._cb_end, on_error=self._cb_error,
        )
        self._player = player
        self._pos_ms = seek_ms
        player.start()
        self._state = "playing"
        self.state_changed.emit("playing")

    def _cb_position(self, ms: int):
        self._pos_ms = ms; self.position_changed.emit(ms)

    def _cb_end(self):
        self._state = "stopped"; self.state_changed.emit("stopped")
        from PyQt5.QtCore import QMetaObject, Qt as _Qt
        QMetaObject.invokeMethod(self, "_advance", _Qt.QueuedConnection)

    def _cb_error(self, msg: str):
        self.error_occurred.emit(f"Playback error: {msg}"); self.state_changed.emit("error")

    @pyqtSlot()
    def _advance(self):
        if self._looping and self._current_track:
            t = self._current_track; t.stream_url = ""; self.load_and_play(t)
        elif self._queue and self._queue_index < len(self._queue) - 1:
            self._queue_index += 1; self.load_and_play(self._queue[self._queue_index])
        else:
            self.queue_ended.emit(self._current_track)

    def _on_poll(self):
        if self._state in ("playing", "paused"):
            self.position_changed.emit(self._pos_ms)
