"""
ui/main_window.py  ─  v5
─────────────────────────
* Uses glass playlist modal instead of QInputDialog.
* Wired to add_to_playlist_current (playbar ➕ button).
* Related tab seeded by smart-autoplay immediately; skeleton shown while waiting.
* Thumbnail fallback: constructs ytimg URL from video ID when thumbnail is empty.
* Removed add-to-queue signal and Settings.
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QAction, QShortcut, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QSettings
from PyQt5.QtGui import QKeySequence

from ui.glass_app import GlassCanvas, PlaylistPickerModal
from core.audio_engine import AudioEngine, TrackInfo
from core.library import Library

_MODE_HOME     = "home"
_MODE_NORMAL   = "normal"
_MODE_ARTIST   = "artist"
_MODE_INFINITE = "infinite"


def _enrich(t: TrackInfo) -> dict:
    """TrackInfo → dict, filling in a fallback thumbnail URL from video ID."""
    thumb = t.thumbnail or (f"https://i.ytimg.com/vi/{t.id}/mqdefault.jpg" if t.id else "")
    return {"id": t.id, "title": t.title, "uploader": t.channel,
            "duration": t.duration, "thumbnail": thumb, "webpage_url": t.webpage_url}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTMusicPlayer")
        self.setMinimumSize(1000,680); self.resize(1340,840)
        self.setStyleSheet(
            "QMainWindow{background:#060210;}"
            "QMenuBar{background:rgba(5,2,14,230);color:rgba(255,255,255,170);"
            "padding:2px 8px;border-bottom:1px solid rgba(255,255,255,8);}"
            "QMenuBar::item{padding:5px 14px;border-radius:6px;}"
            "QMenuBar::item:selected{background:rgba(124,58,237,45);color:white;}"
            "QMenu{background:rgba(14,7,35,252);border:1px solid rgba(255,255,255,12);"
            "border-radius:14px;padding:6px;color:white;}"
            "QMenu::item{padding:8px 22px;border-radius:8px;font-size:13px;}"
            "QMenu::item:selected{background:rgba(124,58,237,50);}"
        )

        self._engine   = AudioEngine(self)
        self._library  = Library(self)
        self._settings = QSettings("YTMusicPlayer","YTMusicPlayer")
        self._tracks:  list = []

        self._search_mode      = _MODE_HOME
        self._pending_q        = ""
        self._pending_artist   = ""
        self._home_loading     = False
        self._current_results  = 0
        self._page_size        = 25
        self._infinite_loading = False
        self._autoplay_pending = False

        self._canvas = GlassCanvas()
        self.setCentralWidget(self._canvas)

        self._sb = QStatusBar(); self._sb.setFixedHeight(22)
        self._sb.setStyleSheet("QStatusBar{background:rgba(4,2,12,210);color:rgba(255,255,255,70);font-size:11px;}")
        self.setStatusBar(self._sb)
        self._sb.showMessage("Ready — double-click a track to play")

        self._wire(); self._build_menu(); self._setup_shortcuts()
        self._restore_settings()
        QTimer.singleShot(400, self._load_home)

    # ── Wiring ────────────────────────────────────────────────────────────────
    def _wire(self):
        c = self._canvas
        c.search_submitted.connect(self._on_search)
        c.track_double_clicked.connect(self._on_activated)
        c.add_to_playlist.connect(self._on_add_pl)
        c.add_to_playlist_current.connect(self._on_add_pl_current)
        c.like_track_sig.connect(self._on_like_track)
        c.nav_changed.connect(self._on_nav)
        c.new_playlist_sig.connect(self._new_playlist)
        c.new_playlist_name_sig.connect(self._new_playlist_named)
        c.play_pause_sig.connect(self._engine.toggle_play_pause)
        c.prev_sig.connect(self._engine.previous_track)
        c.next_sig.connect(self._engine.next_track)
        c.stop_sig.connect(self._engine.stop)
        c.seek_sig.connect(self._engine.seek)
        c.volume_sig.connect(self._engine.set_volume)
        c.like_current_sig.connect(self._toggle_like)
        c.loop_sig.connect(self._engine.set_loop)
        c.artist_search_sig.connect(self._on_artist_search)
        c.scroll_near_bottom.connect(self._on_scroll_near_bottom)

        self._engine.track_changed.connect(self._on_track_changed)
        self._engine.state_changed.connect(lambda s: c.set_playing(s=="playing"))
        self._engine.position_changed.connect(c.set_position)
        self._engine.duration_changed.connect(c.set_duration)
        self._engine.error_occurred.connect(lambda m: self._sb.showMessage(f"⚠ {m}"))
        self._engine.search_results_ready.connect(self._on_results)
        self._engine.queue_ended.connect(self._on_queue_ended)
        self._engine.smart_autoplay_results.connect(self._on_autoplay_results)

        self._library.library_changed.connect(
            lambda: c.update_playlists(self._library.get_playlists()))
        self._engine.set_volume(c.get_volume())

    # ── Menus / shortcuts ─────────────────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        la = QAction("Connect YouTube Account",self); la.triggered.connect(self._show_login); fm.addAction(la)
        fm.addSeparator()
        qa = QAction("Quit",self); qa.setShortcut(QKeySequence.Quit); qa.triggered.connect(self.close); fm.addAction(qa)
        pm = mb.addMenu("Playback")
        for lbl,fn in [("Play / Pause",self._engine.toggle_play_pause),
                        ("Next Track",self._engine.next_track),
                        ("Previous Track",self._engine.previous_track)]:
            a=QAction(lbl,self); a.triggered.connect(fn); pm.addAction(a)
        lm = mb.addMenu("Library")
        np=QAction("New Playlist",self); np.triggered.connect(self._new_playlist); lm.addAction(np)
        ch=QAction("Clear History",self); ch.triggered.connect(self._library.clear_history); lm.addAction(ch)

    def _setup_shortcuts(self):
        for key,fn in [
            ("Space",      self._engine.toggle_play_pause),
            ("Ctrl+Right", self._engine.next_track),
            ("Ctrl+Left",  self._engine.previous_track),
            ("Ctrl+F",     self._canvas.focus_search),
            ("Ctrl+Up",    lambda:self._engine.set_volume(min(100,self._engine.volume+5))),
            ("Ctrl+Down",  lambda:self._engine.set_volume(max(0,  self._engine.volume-5))),
            ("Ctrl+L",     self._toggle_like),
            ("Ctrl+N",     self._new_playlist),
        ]:
            sc=QShortcut(QKeySequence(key),self); sc.activated.connect(fn)

    def _restore_settings(self):
        geo=self._settings.value("geometry")
        if geo: self.restoreGeometry(geo)
        self._engine.set_volume(self._settings.value("volume",70,type=int))
        c=self._settings.value("cookie_file","")
        if c and os.path.exists(c): self._apply_login(c)

    def closeEvent(self,e):
        self._settings.setValue("geometry",self.saveGeometry())
        self._settings.setValue("volume",self._engine.volume)
        self._engine.stop(); super().closeEvent(e)

    # ── Navigation ────────────────────────────────────────────────────────────
    @pyqtSlot(str)
    def _on_nav(self,s:str):
        if   s=="search":              self._canvas.focus_search()
        elif s=="home":                self._load_home()
        elif s=="liked":               self._load_liked()
        elif s=="history":             self._load_history()
        elif s.startswith("playlist:"): self._load_playlist(s.split(":",1)[1])

    def _load_home(self):
        self._canvas.set_section("Discover","Popular tracks right now")
        self._canvas.show_loading_skeleton(10)
        self._home_loading=True; self._search_mode=_MODE_HOME
        self._pending_q="top hits 2024"; self._current_results=0
        self._engine.search("top hits 2024",max_results=self._page_size)

    def _load_liked(self):
        d=self._library.get_liked(); self._tracks=d
        self._canvas.set_section("Liked Songs",f"{len(d)} tracks")
        if d: self._canvas.set_tracks(d)
        else: self._canvas.show_status("No liked songs yet.")

    def _load_history(self):
        d=self._library.get_history(); self._tracks=d
        self._canvas.set_section("Recently Played",f"{len(d)} tracks")
        if d: self._canvas.set_tracks(d)
        else: self._canvas.show_status("Nothing played yet.")

    def _load_playlist(self,pid:str):
        pl=self._library.get_playlists(); info=pl.get(pid,{})
        d=self._library.get_playlist_tracks(pid); self._tracks=d
        self._canvas.set_section(info.get("name","Playlist"),f"{len(d)} tracks")
        if d: self._canvas.set_tracks(d)
        else: self._canvas.show_status("Playlist is empty.")

    # ── Search ────────────────────────────────────────────────────────────────
    @pyqtSlot(str)
    def _on_search(self,q:str):
        self._canvas.set_search_loading(True)
        self._canvas.set_section(f'Search: "{q}"',"Searching…")
        self._canvas.show_loading_skeleton(8)
        self._home_loading=False; self._search_mode=_MODE_NORMAL
        self._pending_q=q; self._current_results=0; self._infinite_loading=False
        self._engine.search(q,max_results=self._page_size)

    @pyqtSlot(str)
    def _on_artist_search(self,artist:str):
        if not artist or artist=="—": return
        self._canvas.set_search_loading(True)
        self._canvas.set_section(f"🎤  {artist}","Loading…")
        self._canvas.show_loading_skeleton(8)
        self._home_loading=False; self._search_mode=_MODE_ARTIST
        self._pending_q=f"{artist} official audio"; self._pending_artist=artist
        self._current_results=0; self._infinite_loading=False
        self._engine.search(f"{artist} official audio",max_results=30)
        self._sb.showMessage(f"Loading artist: {artist}")

    @pyqtSlot()
    def _on_scroll_near_bottom(self):
        if self._search_mode not in (_MODE_NORMAL,_MODE_HOME): return
        if self._infinite_loading: return
        self._infinite_loading=True
        new_max=self._current_results+self._page_size
        self._search_mode=_MODE_INFINITE
        self._sb.showMessage("Loading more tracks…")
        self._canvas.append_skeleton_rows(4)
        self._engine.search(self._pending_q,max_results=new_max)

    @pyqtSlot(list)
    def _on_results(self,results:list):
        tracks=[_enrich(t) for t in results]

        if self._search_mode==_MODE_INFINITE:
            existing={t.get("id") for t in self._tracks}
            fresh=[t for t in tracks if t.get("id") not in existing]
            if fresh:
                self._tracks.extend(fresh); self._canvas.append_tracks(fresh)
                self._current_results=len(self._tracks)
                self._canvas.set_section(self._canvas._section_title,f"{self._current_results} tracks")
            self._infinite_loading=False
            self._search_mode=_MODE_NORMAL if self._pending_q else _MODE_HOME
            return

        if self._search_mode==_MODE_ARTIST:
            self._tracks=tracks; self._current_results=len(tracks)
            self._canvas.set_search_loading(False)
            self._canvas.show_artist_profile(self._pending_artist,tracks)
            self._canvas.set_section(f"🎤  {self._pending_artist}",f"{len(tracks)} tracks found")
            return

        if self._home_loading or self._search_mode==_MODE_HOME:
            self._home_loading=False; self._search_mode=_MODE_HOME
            self._tracks=tracks; self._current_results=len(tracks)
            self._canvas.set_section("Discover","Popular tracks right now")
            if tracks: self._canvas.set_tracks(tracks)
            else: self._canvas.show_status("No results found.")
            return

        q=self._pending_q; n=len(tracks)
        self._tracks=tracks; self._current_results=n
        self._canvas.set_section(f'"{q}"',f"{n} result{'s' if n!=1 else ''}")
        self._canvas.set_search_loading(False)
        if tracks: self._canvas.set_tracks(tracks)
        else: self._canvas.show_status("No results found.")

    # ── Playback ──────────────────────────────────────────────────────────────
    @pyqtSlot(dict,int)
    def _on_activated(self,t:dict,idx:int):
        self._engine.set_queue([TrackInfo(x) for x in self._tracks],idx)
        self._canvas.set_current_index(idx)
        # Immediately seed the overlay with the full engine queue
        engine_queue_dicts=[_enrich(q) for q in self._engine.queue]
        self._canvas.update_queue_display(engine_queue_dicts, idx)

    @pyqtSlot(object)
    def _on_track_changed(self,track:TrackInfo):
        self._canvas.set_track_info(track.title,track.channel)
        thumb=track.thumbnail or (f"https://i.ytimg.com/vi/{track.id}/mqdefault.jpg" if track.id else "")
        if thumb: self._canvas.set_thumbnail(thumb)
        self._canvas.set_liked(self._library.is_liked(track.id))
        self._library.add_to_history(_enrich(track))
        self._sb.showMessage(f"Now playing: {track.title}")
        # Pass the ENGINE's queue (as dicts) to the overlay — not the display list
        engine_queue_dicts = [_enrich(t) for t in self._engine.queue]
        self._canvas.update_queue_display(engine_queue_dicts, self._engine.queue_index)
        # Seed Related tab with similar tracks for the new track
        if not self._autoplay_pending:
            self._autoplay_pending = True
            self._engine.search_similar(track, max_results=12)

    @pyqtSlot(object)
    def _on_queue_ended(self,last_track):
        """Queue ran out — extend it from the Related cache."""
        if not last_track: return
        cached = self._canvas._exp._cached_related
        if cached:
            fresh_ti = [TrackInfo(d) for d in cached
                        if d.get("id") not in {t.id for t in self._engine.queue}]
            if fresh_ti:
                fresh_dicts = [_enrich(t) for t in fresh_ti]
                self._tracks.extend(fresh_dicts)
                self._canvas.append_tracks(fresh_dicts)
                prev_len = len(self._engine.queue)
                self._engine.extend_queue(fresh_ti)
                self._engine._queue_index = prev_len
                self._engine.load_and_play(self._engine.queue[prev_len])
                self._sb.showMessage(f"▶ Smart autoplay: queued {len(fresh_ti)} similar tracks")
                return
        # Nothing cached yet — trigger a fresh search
        if not self._autoplay_pending:
            self._autoplay_pending = True
            self._engine.search_similar(last_track, max_results=12)

    @pyqtSlot(list)
    def _on_autoplay_results(self,results:list):
        """Populate the Related tab; do NOT auto-advance (queue_ended handles that)."""
        self._autoplay_pending = False
        if not results: return
        result_dicts = [_enrich(t) for t in results]
        self._canvas.set_related_tracks(result_dicts)

    # ── Library ───────────────────────────────────────────────────────────────
    def _toggle_like(self):
        t=self._engine.current_track
        if not t: return
        if self._library.is_liked(t.id):
            self._library.unlike_track(t.id); self._canvas.set_liked(False)
        else:
            self._library.like_track(_enrich(t)); self._canvas.set_liked(True)

    @pyqtSlot(dict)
    def _on_like_track(self,t:dict):
        vid=t.get("id","")
        if self._library.is_liked(vid): self._library.unlike_track(vid)
        else: self._library.like_track(t)

    @pyqtSlot(dict)
    def _on_add_pl(self,t:dict):
        """Add a specific track to a playlist (from context menu)."""
        pl=self._library.get_playlists()
        if not pl:
            QMessageBox.information(self,"No Playlists","Create a playlist first (Ctrl+N)."); return
        pid=self._canvas.show_playlist_picker(pl)
        if pid: self._library.add_to_playlist(pid,t)

    @pyqtSlot()
    def _on_add_pl_current(self):
        """Add the currently playing track to a playlist (playbar ➕ button)."""
        t=self._engine.current_track
        if not t: return
        pl=self._library.get_playlists()
        if not pl:
            QMessageBox.information(self,"No Playlists","Create a playlist first (Ctrl+N)."); return
        pid=self._canvas.show_playlist_picker(pl)
        if pid: self._library.add_to_playlist(pid,_enrich(t))

    def _new_playlist(self):
        """Fallback: called from Ctrl+N and menu — opens glass modal directly."""
        name = self._canvas.show_new_playlist_modal()
        if name and name.strip():
            self._library.create_playlist(name.strip())

    def _new_playlist_named(self, name: str):
        """Called from the sidebar ＋ button via new_playlist_name_sig."""
        if name and name.strip():
            self._library.create_playlist(name.strip())

    # ── Login ──────────────────────────────────────────────────────────────────
    def _show_login(self):
        from ui.login_dialog import LoginDialog
        d=LoginDialog(self); d.login_successful.connect(self._apply_login); d.exec_()

    @pyqtSlot(str)
    def _apply_login(self,path:str):
        self._engine.set_cookie_file(path)
        self._settings.setValue("cookie_file",path)
        self._sb.showMessage("Connected to YouTube")
