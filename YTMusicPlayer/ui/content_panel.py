"""ui/content_panel.py — Premium glass content panel."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QBrush

from ui.track_list import TrackList


class ContentPanel(QWidget):
    track_activated=pyqtSignal(dict,int)
    add_to_queue=pyqtSignal(dict)
    add_to_playlist=pyqtSignal(dict)
    like_track=pyqtSignal(dict)
    search_requested=pyqtSignal(str)

    _HINTS=[
        "Search songs, artists, albums…",
        "Try: lofi chill beats",
        "Try: The Weeknd Blinding Lights",
        "Try: phonk drift montagem",
        "Try: jazz study session",
        "Try: OPM hits Philippines",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contentPanel")
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._build()

    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # Search bar
        sc=QWidget(); sc.setObjectName("searchContainer")
        sw=QHBoxLayout(sc); sw.setContentsMargins(24,14,24,14); sw.setSpacing(12)
        self._input=QLineEdit(); self._input.setObjectName("searchBar")
        self._input.setMinimumHeight(46); self._input.returnPressed.connect(self._submit)
        self._btn=QPushButton("Search"); self._btn.setObjectName("searchBtn")
        self._btn.setFixedHeight(46); self._btn.setFixedWidth(96)
        self._btn.clicked.connect(self._submit)
        sw.addWidget(self._input,1); sw.addWidget(self._btn)
        lay.addWidget(sc)

        # Header
        self._hdr=QWidget(); self._hdr.setStyleSheet("background:transparent;")
        hl=QVBoxLayout(self._hdr); hl.setContentsMargins(24,20,24,10); hl.setSpacing(4)
        self._h_title=QLabel("Home"); self._h_title.setObjectName("sectionTitle")
        self._h_sub=QLabel(""); self._h_sub.setObjectName("sectionSubtitle")
        hl.addWidget(self._h_title); hl.addWidget(self._h_sub)
        lay.addWidget(self._hdr)

        # Status label
        self._status=QLabel(""); self._status.setObjectName("statusMsg")
        self._status.setAlignment(Qt.AlignCenter); self._status.hide()
        lay.addWidget(self._status)

        # Track list
        self._tracks=TrackList()
        self._tracks.track_activated.connect(self.track_activated)
        self._tracks.add_to_queue.connect(self.add_to_queue)
        self._tracks.add_to_playlist.connect(self.add_to_playlist)
        self._tracks.like_track.connect(self.like_track)
        lay.addWidget(self._tracks,1)

        # Hint cycling
        self._hi=0
        t=QTimer(self); t.timeout.connect(self._cycle); t.start(3200)

    def _cycle(self):
        self._hi=(self._hi+1)%len(self._HINTS)
        self._input.setPlaceholderText(self._HINTS[self._hi])

    def _submit(self):
        q=self._input.text().strip()
        if q: self.search_requested.emit(q)

    def show_section(self,title,subtitle,tracks):
        self._h_title.setText(title); self._h_sub.setText(subtitle)
        self._status.hide()
        if tracks: self._tracks.set_tracks(tracks)
        else: self._status.setText("Nothing here yet."); self._status.show()

    def show_search_results(self,tracks,query):
        self._h_title.setText(f'Search: "{query}"')
        self._h_sub.setText(f"{len(tracks)} results")
        self._btn.setText("Search"); self._btn.setEnabled(True); self._input.setEnabled(True)
        self._status.hide()
        if tracks: self._tracks.set_tracks(tracks)
        else: self._status.setText(f'No results for "{query}"'); self._status.show()

    def show_loading(self,msg="Loading…"):
        self._status.setText(f"⏳  {msg}"); self._status.show(); self._tracks.clear()

    def show_error(self,msg):
        self._status.setText(f"⚠  {msg}"); self._status.show()
        self._btn.setText("Search"); self._btn.setEnabled(True)

    def set_search_loading(self,on):
        self._btn.setText("…" if on else "Search")
        self._btn.setEnabled(not on); self._input.setEnabled(not on)

    def set_current_track_index(self,i): self._tracks.set_current_index(i)
    def focus_search(self): self._input.setFocus()

    def paintEvent(self,e):
        p=QPainter(self)
        # Very subtle gradient that lets lava lamp bleed through
        g=QLinearGradient(0,0,0,self.height())
        g.setColorAt(0.0, QColor(5,2,16,45))
        g.setColorAt(0.4, QColor(8,3,22,40))
        g.setColorAt(1.0, QColor(5,2,14,50))
        p.fillRect(self.rect(),g)
        p.end()
        super().paintEvent(e)
