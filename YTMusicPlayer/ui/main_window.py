"""ui/main_window.py — MainWindow using single GlassCanvas."""
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QStatusBar,
    QAction, QShortcut, QInputDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QSettings
from PyQt5.QtGui import QKeySequence

from ui.glass_app import GlassCanvas
from core.audio_engine import AudioEngine, TrackInfo
from core.library import Library
from core.yt_fetcher import YTFetcher


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTMusicPlayer")
        self.setMinimumSize(1000,680); self.resize(1340,840)
        self.setStyleSheet("QMainWindow{background:#060210;} QMenuBar{background:rgba(5,2,14,230);color:rgba(255,255,255,170);padding:2px 8px;border-bottom:1px solid rgba(255,255,255,8);} QMenuBar::item{padding:5px 14px;border-radius:6px;} QMenuBar::item:selected{background:rgba(124,58,237,45);color:white;} QMenu{background:rgba(14,7,35,252);border:1px solid rgba(255,255,255,12);border-radius:14px;padding:6px;color:white;} QMenu::item{padding:8px 22px;border-radius:8px;font-size:13px;} QMenu::item:selected{background:rgba(124,58,237,50);}")

        self._engine   = AudioEngine(self)
        self._library  = Library(self)
        self._settings = QSettings("YTMusicPlayer","YTMusicPlayer")
        self._tracks   = []
        self._home_loading = False

        # Single canvas widget
        self._canvas = GlassCanvas()
        self.setCentralWidget(self._canvas)

        self._sb = QStatusBar(); self._sb.setFixedHeight(22)
        self._sb.setStyleSheet("QStatusBar{background:rgba(4,2,12,210);color:rgba(255,255,255,70);font-size:11px;}")
        self.setStatusBar(self._sb)
        self._sb.showMessage("Ready — double-click a track to play")

        self._wire()
        self._build_menu()
        self._setup_shortcuts()
        self._restore_settings()
        QTimer.singleShot(400, self._load_home)

    def _wire(self):
        c=self._canvas
        c.search_submitted.connect(self._on_search)
        c.track_double_clicked.connect(self._on_activated)
        c.add_to_queue.connect(lambda t:self._engine.append_to_queue(TrackInfo(t)))
        c.add_to_playlist.connect(self._on_add_pl)
        c.like_track_sig.connect(self._on_like_track)
        c.nav_changed.connect(self._on_nav)
        c.new_playlist_sig.connect(self._new_playlist)
        c.play_pause_sig.connect(self._engine.toggle_play_pause)
        c.prev_sig.connect(self._engine.previous_track)
        c.next_sig.connect(self._engine.next_track)
        c.stop_sig.connect(self._engine.stop)
        c.seek_sig.connect(self._engine.seek)
        c.volume_sig.connect(self._engine.set_volume)
        c.like_current_sig.connect(self._toggle_like)
        c.loop_sig.connect(self._engine.set_loop)

        self._engine.track_changed.connect(self._on_track_changed)
        self._engine.state_changed.connect(lambda s:c.set_playing(s=="playing"))
        self._engine.position_changed.connect(c.set_position)
        self._engine.duration_changed.connect(c.set_duration)
        self._engine.error_occurred.connect(lambda m:self._sb.showMessage(f"⚠ {m}"))
        self._engine.search_results_ready.connect(self._on_results)
        self._library.library_changed.connect(lambda:c.update_playlists(self._library.get_playlists()))
        self._engine.set_volume(c.get_volume())

    def _build_menu(self):
        mb=self.menuBar()
        fm=mb.addMenu("File")
        la=QAction("Connect YouTube Account",self); la.triggered.connect(self._show_login); fm.addAction(la)
        fm.addSeparator()
        qa=QAction("Quit",self); qa.setShortcut(QKeySequence.Quit); qa.triggered.connect(self.close); fm.addAction(qa)
        pm=mb.addMenu("Playback")
        for lbl,key,fn in[("Play / Pause","Space",self._engine.toggle_play_pause),
                           ("Next","Ctrl+Right",self._engine.next_track),
                           ("Previous","Ctrl+Left",self._engine.previous_track)]:
            a=QAction(lbl,self); a.setShortcut(QKeySequence(key)); a.triggered.connect(fn); pm.addAction(a)
        lm=mb.addMenu("Library")
        np=QAction("New Playlist",self); np.triggered.connect(self._new_playlist); lm.addAction(np)
        ch=QAction("Clear History",self); ch.triggered.connect(self._library.clear_history); lm.addAction(ch)

    def _setup_shortcuts(self):
        for key,fn in[("Space",self._engine.toggle_play_pause),
                      ("Ctrl+Right",self._engine.next_track),("Ctrl+Left",self._engine.previous_track),
                      ("Ctrl+F",self._canvas.focus_search),
                      ("Ctrl+Up",lambda:self._engine.set_volume(min(100,self._engine.volume+5))),
                      ("Ctrl+Down",lambda:self._engine.set_volume(max(0,self._engine.volume-5))),
                      ("Ctrl+L",self._toggle_like),("Ctrl+N",self._new_playlist)]:
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

    @pyqtSlot(str)
    def _on_nav(self,s:str):
        if s=="search": self._canvas.focus_search()
        elif s=="home": self._load_home()
        elif s=="liked": self._load_liked()
        elif s=="history": self._load_history()
        elif s.startswith("playlist:"): self._load_playlist(s.split(":",1)[1])

    def _load_home(self):
        self._canvas.set_section("Discover","Popular tracks right now")
        self._canvas.show_status("⏳  Loading popular tracks…")
        self._home_loading=True; self._engine.search("top hits 2024",max_results=25)

    def _load_liked(self):
        d=self._library.get_liked(); self._tracks=d
        self._canvas.set_section("Liked Songs",f"{len(d)} tracks")
        if d: self._canvas.set_tracks(d)
        else: self._canvas.show_status("No liked songs yet. Like a track to save it here.")

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

    @pyqtSlot(str)
    def _on_search(self,q:str):
        self._canvas.set_search_loading(True)
        self._canvas.set_section(f'Search: "{q}"',"Searching…")
        self._canvas.show_status("⏳  Searching…")
        self._home_loading=False; self._pending_q=q
        self._engine.search(q,max_results=25)

    @pyqtSlot(list)
    def _on_results(self,results:list):
        tracks=[{"id":t.id,"title":t.title,"uploader":t.channel,"duration":t.duration,
                 "thumbnail":t.thumbnail,"webpage_url":t.webpage_url} for t in results]
        self._tracks=tracks
        if self._home_loading:
            self._home_loading=False
            self._canvas.set_section("Discover","Popular tracks right now")
        else:
            q=getattr(self,"_pending_q","")
            n=len(tracks)
            self._canvas.set_section(f'"{q}"',f"{n} result{'s' if n!=1 else ''}")
            self._canvas.set_search_loading(False)
        if tracks: self._canvas.set_tracks(tracks)
        else: self._canvas.show_status("No results found.")

    @pyqtSlot(dict,int)
    def _on_activated(self,t:dict,idx:int):
        self._engine.set_queue([TrackInfo(x) for x in self._tracks],idx)
        self._canvas.set_current_index(idx)

    @pyqtSlot(object)
    def _on_track_changed(self,track:TrackInfo):
        self._canvas.set_track_info(track.title,track.channel)
        if track.thumbnail: self._canvas.set_thumbnail(track.thumbnail)
        self._canvas.set_liked(self._library.is_liked(track.id))
        self._library.add_to_history({"id":track.id,"title":track.title,"uploader":track.channel,
            "duration":track.duration,"thumbnail":track.thumbnail,"webpage_url":track.webpage_url})
        self._sb.showMessage(f"Now playing: {track.title}")

    def _toggle_like(self):
        t=self._engine.current_track
        if not t: return
        if self._library.is_liked(t.id): self._library.unlike_track(t.id); self._canvas.set_liked(False)
        else:
            self._library.like_track({"id":t.id,"title":t.title,"uploader":t.channel,
                "duration":t.duration,"thumbnail":t.thumbnail,"webpage_url":t.webpage_url})
            self._canvas.set_liked(True)

    @pyqtSlot(dict)
    def _on_like_track(self,t:dict):
        vid=t.get("id","")
        if self._library.is_liked(vid): self._library.unlike_track(vid)
        else: self._library.like_track(t)

    @pyqtSlot(dict)
    def _on_add_pl(self,t:dict):
        pl=self._library.get_playlists()
        if not pl: QMessageBox.information(self,"No Playlists","Create a playlist first."); return
        names=[i["name"] for i in pl.values()]; pids=list(pl.keys())
        name,ok=QInputDialog.getItem(self,"Add to Playlist","Select:",names,0,False)
        if ok and name: self._library.add_to_playlist(pids[names.index(name)],t)

    def _new_playlist(self):
        name,ok=QInputDialog.getText(self,"New Playlist","Name:")
        if ok and name.strip(): self._library.create_playlist(name.strip())

    def _show_login(self):
        from ui.login_dialog import LoginDialog
        d=LoginDialog(self); d.login_successful.connect(self._apply_login); d.exec_()

    @pyqtSlot(str)
    def _apply_login(self,path:str):
        self._engine.set_cookie_file(path)
        self._settings.setValue("cookie_file",path)
        self._sb.showMessage("Connected to YouTube")
