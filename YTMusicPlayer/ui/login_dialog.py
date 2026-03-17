"""
ui/login_dialog.py
──────────────────
Login dialog that guides users to export browser cookies for
authenticated YouTube access (history, liked songs, playlists).

Two methods:
  1. Automatic browser cookie extraction (via yt-dlp --cookies-from-browser)
  2. Manual cookie file path entry
"""

import os
import threading
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTabWidget, QWidget, QMessageBox,
    QProgressBar,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPainter, QColor

from ui.theme import ACCENT_PURPLE, ACCENT_PINK, TEXT_MUTED, GLASS_BORDER


class CookieExtractThread(QThread):
    """Background thread to test a cookie file with yt-dlp."""

    result = pyqtSignal(bool, str)  # success, message

    def __init__(self, cookie_path: str):
        super().__init__()
        self.cookie_path = cookie_path

    def run(self):
        try:
            import yt_dlp
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "cookiefile": self.cookie_path,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Try to access the liked-videos playlist — requires login
                info = ydl.extract_info(
                    "https://www.youtube.com/playlist?list=LL",
                    download=False,
                )
            self.result.emit(True, "Login successful! Personalised content enabled.")
        except Exception as e:
            msg = str(e)
            if "Sign in" in msg or "cookie" in msg.lower():
                self.result.emit(False, "Cookies don't grant access. Please re-export.")
            else:
                self.result.emit(False, f"Error: {msg[:120]}")


class LoginDialog(QDialog):
    """
    Modal dialog for YouTube authentication.

    Signals
    -------
    login_successful(str)   — path to the valid cookie file
    """

    login_successful = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to YouTube")
        self.setMinimumWidth(500)
        self.setMinimumHeight(360)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._cookie_path = ""
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: rgba(15, 8, 35, 0.97);
                border: 1px solid {GLASS_BORDER};
                border-radius: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(16)

        # Title
        title = QLabel("Connect to YouTube")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: white;")
        card_layout.addWidget(title)

        sub = QLabel(
            "To access your liked songs, history, and playlists,\n"
            "you need to provide your browser's YouTube cookies."
        )
        sub.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        sub.setWordWrap(True)
        card_layout.addWidget(sub)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {GLASS_BORDER}; border-radius: 8px; background: transparent; }}
            QTabBar::tab {{ background: rgba(255,255,255,8); color: {TEXT_MUTED}; padding: 7px 18px; border-radius: 6px; margin-right: 4px; }}
            QTabBar::tab:selected {{ background: rgba(155,93,229,0.35); color: white; }}
        """)

        # Tab 1: Instructions
        instr_tab = QWidget()
        instr_layout = QVBoxLayout(instr_tab)
        instr_layout.setContentsMargins(12, 12, 12, 12)

        steps = QLabel(
            "1. Install the <b>cookies.txt</b> browser extension\n"
            "   (Firefox: cookies.txt / Chrome: Get cookies.txt LOCALLY)\n\n"
            "2. Visit <b>youtube.com</b> and make sure you're logged in\n\n"
            "3. Click the extension → Export cookies for <b>youtube.com</b>\n\n"
            "4. Save the file and browse to it below"
        )
        steps.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; line-height: 160%;")
        steps.setWordWrap(True)
        instr_layout.addWidget(steps)
        tabs.addTab(instr_tab, "📋  How to")

        # Tab 2: File picker
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(12, 16, 12, 12)
        file_layout.setSpacing(10)

        row = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Path to cookies.txt file…")
        self._path_input.setMinimumHeight(38)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedHeight(38)
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self._path_input, 1)
        row.addWidget(browse_btn)
        file_layout.addLayout(row)

        self._test_btn = QPushButton("Verify & Connect")
        self._test_btn.setFixedHeight(40)
        self._test_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT_PURPLE}, stop:1 {ACCENT_PINK});
                border: none; border-radius: 8px;
                color: white; font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.85; }}
            QPushButton:disabled {{ background: rgba(255,255,255,15); color: rgba(255,255,255,60); }}
        """)
        self._test_btn.clicked.connect(self._verify)
        file_layout.addWidget(self._test_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ border: none; background: rgba(255,255,255,10); border-radius: 2px; }}
            QProgressBar::chunk {{ background: {ACCENT_PURPLE}; border-radius: 2px; }}
        """)
        self._progress.hide()
        file_layout.addWidget(self._progress)

        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        self._result_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        file_layout.addWidget(self._result_lbl)
        file_layout.addStretch()

        tabs.addTab(file_tab, "📂  Cookie File")
        tabs.setCurrentIndex(1)
        card_layout.addWidget(tabs, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        skip_btn = QPushButton("Skip — Browse without login")
        skip_btn.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none;")
        skip_btn.clicked.connect(self.reject)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("background: rgba(255,255,255,10); border-radius: 16px; color: white;")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        card_layout.addLayout(btn_row)

        outer.addWidget(card)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select cookies.txt", os.path.expanduser("~"),
            "Cookie files (*.txt);;All files (*)"
        )
        if path:
            self._path_input.setText(path)

    def _verify(self):
        path = self._path_input.text().strip()
        if not path or not os.path.exists(path):
            self._result_lbl.setText("⚠  File not found.")
            self._result_lbl.setStyleSheet("color: #F72585;")
            return

        self._test_btn.setEnabled(False)
        self._progress.show()
        self._result_lbl.setText("Verifying cookies…")
        self._result_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        self._cookie_path = path

        self._thread = CookieExtractThread(path)
        self._thread.result.connect(self._on_result)
        self._thread.start()

    @pyqtSlot(bool, str)
    def _on_result(self, success: bool, message: str):
        self._progress.hide()
        self._test_btn.setEnabled(True)
        self._result_lbl.setText(("✓  " if success else "✗  ") + message)
        colour = "#4CC9F0" if success else "#F72585"
        self._result_lbl.setStyleSheet(f"color: {colour};")
        if success:
            self.login_successful.emit(self._cookie_path)
            QTimer_single = __import__("PyQt5.QtCore", fromlist=["QTimer"]).QTimer
            QTimer_single.singleShot(1200, self.accept)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()
        super().paintEvent(event)
