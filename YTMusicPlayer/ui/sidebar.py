"""ui/sidebar.py — Premium frosted glass sidebar."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen


class Sidebar(QWidget):
    section_changed           = pyqtSignal(str)
    new_playlist_requested    = pyqtSignal()
    delete_playlist_requested = pyqtSignal(str)

    _NAV = [
        ("search",  "🔍", "Search"),
        ("home",    "🏠", "Home"),
        ("liked",   "♥",  "Liked Songs"),
        ("history", "🕐", "History"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarPanel")
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAutoFillBackground(False)
        self._btns: dict = {}
        self._pl_btns: dict = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 16)
        layout.setSpacing(2)

        # Logo
        logo = QLabel("▶  YTMusicPlayer")
        logo.setObjectName("appTitle")
        layout.addWidget(logo)

        # Divider
        layout.addWidget(self._divider())
        layout.addSpacing(6)

        # Nav buttons
        for sid, icon, label in self._NAV:
            btn = self._make_btn(f"  {icon}   {label}", sid)
            self._btns[sid] = btn
            layout.addWidget(btn)

        layout.addSpacing(8)
        layout.addWidget(self._divider())

        # Library section
        lbl = QLabel("LIBRARY")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        new_btn = QPushButton("  ＋   New Playlist")
        new_btn.setObjectName("newPlaylistBtn")
        new_btn.setMinimumHeight(36)
        new_btn.clicked.connect(self.new_playlist_requested)
        layout.addWidget(new_btn)

        # Playlist scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        self._pl_container = QWidget()
        self._pl_layout = QVBoxLayout(self._pl_container)
        self._pl_layout.setContentsMargins(0,0,0,0)
        self._pl_layout.setSpacing(2)
        self._pl_layout.addStretch()
        scroll.setWidget(self._pl_container)
        layout.addWidget(scroll, 1)

        layout.addWidget(self._divider())

        # Settings
        settings = self._make_btn("  ⚙   Settings", "settings")
        self._btns["settings"] = settings
        layout.addWidget(settings)

        self._activate("home")

    def _make_btn(self, label, sid):
        btn = QPushButton(label)
        btn.setObjectName("navBtn")
        btn.setCheckable(True)
        btn.setAutoExclusive(False)
        btn.setMinimumHeight(42)
        btn.setFlat(True)
        btn.clicked.connect(lambda _, s=sid: self._activate(s))
        return btn

    def _divider(self):
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet("background: rgba(255,255,255,10); margin: 4px 4px;")
        return f

    def _activate(self, section):
        for btn in list(self._btns.values()) + list(self._pl_btns.values()):
            btn.setChecked(False)
        key = section.replace("playlist:", "")
        target = self._pl_btns.get(key) or self._btns.get(section)
        if target: target.setChecked(True)
        self.section_changed.emit(section)

    def update_playlists(self, playlists: dict):
        for btn in self._pl_btns.values(): btn.setParent(None)
        self._pl_btns.clear()
        self._pl_layout.takeAt(self._pl_layout.count()-1)
        for pid, info in playlists.items():
            btn = self._make_btn(f"  📋   {info.get('name','Untitled')}", f"playlist:{pid}")
            btn.setMinimumHeight(36)
            self._pl_layout.addWidget(btn)
            self._pl_btns[pid] = btn
        self._pl_layout.addStretch()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(p.Antialiasing)
        # Frosted glass: dark semi-transparent with very subtle gradient
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0.0, QColor(10, 4, 25, 80))
        g.setColorAt(1.0, QColor(6,  2, 18, 70))
        p.fillRect(self.rect(), g)
        # Right edge gleam
        gleam = QLinearGradient(self.width()-2, 0, self.width(), 0)
        gleam.setColorAt(0, QColor(255,255,255,0))
        gleam.setColorAt(1, QColor(255,255,255,12))
        p.fillRect(self.width()-2, 0, 2, self.height(), gleam)
        p.end()
        super().paintEvent(e)
