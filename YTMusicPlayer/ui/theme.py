"""ui/theme.py — Premium glassmorphism stylesheet."""

APP_STYLESHEET = """
/* ═══════════════════════════════════════════════════════════════════════════
   BASE
═══════════════════════════════════════════════════════════════════════════ */
* {
    color: #FFFFFF;
    font-family: "Segoe UI", "SF Pro Display", Arial, sans-serif;
    font-size: 13px;
    border: none; outline: none; margin: 0; padding: 0;
    selection-background-color: rgba(147,51,234,120);
}
QMainWindow { background: #060210; }
QWidget     { background: transparent; }
QWidget#sidebarPanel  { background: transparent; }
QWidget#contentPanel  { background: transparent; }
QWidget#playerPanel   { background: transparent; }
QWidget#searchContainer { background: rgba(255,255,255,3); }

/* ═══════════════════════════════════════════════════════════════════════════
   SIDEBAR  — frosted glass panel
═══════════════════════════════════════════════════════════════════════════ */
#sidebarPanel {
    min-width: 230px; max-width: 230px;
    border-right: 1px solid rgba(255,255,255,12);
}
#appTitle {
    font-size: 17px; font-weight: 700; color: white;
    padding: 22px 20px 14px 20px; letter-spacing: 0.3px;
}
#sectionLabel {
    font-size: 10px; font-weight: 600; letter-spacing: 2.5px;
    color: rgba(255,255,255,55); padding: 14px 20px 5px 20px;
}
#navBtn {
    background: transparent; border: none; border-radius: 12px;
    padding: 10px 18px; text-align: left;
    color: rgba(255,255,255,140); font-size: 13px; font-weight: 400;
}
#navBtn:hover {
    background: rgba(255,255,255,8);
    color: rgba(255,255,255,220);
}
#navBtn:checked {
    background: rgba(147,51,234,30);
    color: white; font-weight: 500;
    border: 1px solid rgba(147,51,234,45);
}
#newPlaylistBtn {
    background: transparent; border: none; border-radius: 12px;
    padding: 8px 18px; text-align: left;
    color: rgba(167,139,250,180); font-size: 12px;
}
#newPlaylistBtn:hover { background: rgba(147,51,234,15); color: #c4b5fd; }

/* ═══════════════════════════════════════════════════════════════════════════
   CONTENT PANEL
═══════════════════════════════════════════════════════════════════════════ */
#contentPanel { border-left: 1px solid rgba(255,255,255,8); }

#searchContainer {
    background: rgba(255,255,255,4);
    border-bottom: 1px solid rgba(255,255,255,8);
    padding: 0px;
}
#searchBar {
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,15);
    border-radius: 28px;
    padding: 12px 24px; font-size: 14px; color: white;
}
#searchBar:focus {
    background: rgba(147,51,234,10);
    border: 1px solid rgba(147,51,234,120);
}
#searchBtn {
    background: rgba(255,255,255,10);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 28px;
    padding: 12px 28px; color: white;
    font-weight: 600; font-size: 13px;
}
#searchBtn:hover {
    background: rgba(147,51,234,40);
    border-color: rgba(147,51,234,80);
}
#searchBtn:pressed { background: rgba(147,51,234,60); }

#sectionTitle    { font-size: 28px; font-weight: 700; color: white; letter-spacing: -0.5px; }
#sectionSubtitle { font-size: 12px; color: rgba(255,255,255,80); margin-top: 2px; }
#statusMsg       { font-size: 14px; color: rgba(255,255,255,60); padding: 40px; }

/* ═══════════════════════════════════════════════════════════════════════════
   TRACK LIST
═══════════════════════════════════════════════════════════════════════════ */
QListWidget {
    background: transparent; border: none; outline: none;
    padding: 0px 8px;
}
QListWidget::item {
    background: transparent; border-radius: 12px;
    color: rgba(255,255,255,160); padding: 0px;
    margin: 1px 0px;
}
QListWidget::item:hover {
    background: rgba(255,255,255,5);
    color: white;
}
QListWidget::item:selected {
    background: rgba(147,51,234,18);
    color: white;
    border: 1px solid rgba(147,51,234,30);
}

/* ═══════════════════════════════════════════════════════════════════════════
   SCROLLBARS
═══════════════════════════════════════════════════════════════════════════ */
QScrollBar:vertical   { background:transparent; width:4px; margin:0; }
QScrollBar::handle:vertical { background:rgba(255,255,255,18); border-radius:2px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:4px; }
QScrollBar::handle:horizontal { background:rgba(255,255,255,18); border-radius:2px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }

/* ═══════════════════════════════════════════════════════════════════════════
   PLAYER BAR
═══════════════════════════════════════════════════════════════════════════ */
#playerPanel {
    border-top: 1px solid rgba(255,255,255,10);
    min-height: 96px; max-height: 96px;
}
#trackTitle  { font-size: 14px; font-weight: 600; color: white; }
#trackArtist { font-size: 11px; color: rgba(255,255,255,120); margin-top: 2px; }
#timeLabel   { font-size: 11px; color: rgba(255,255,255,80); min-width: 36px; }

/* Volume slider */
#volSlider::groove:horizontal {
    background: rgba(255,255,255,15); height:3px; border-radius:2px;
}
#volSlider::sub-page:horizontal {
    background: rgba(167,139,250,180); border-radius:2px;
}
#volSlider::handle:horizontal {
    background: white; border: 2px solid rgba(147,51,234,200);
    width:10px; height:10px; margin:-3px 0; border-radius:5px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   MENUS & DIALOGS
═══════════════════════════════════════════════════════════════════════════ */
QMenuBar {
    background: rgba(5,2,14,230); color: rgba(255,255,255,180); padding: 2px 8px;
    border-bottom: 1px solid rgba(255,255,255,8);
}
QMenuBar::item { padding: 5px 14px; border-radius: 6px; }
QMenuBar::item:selected { background: rgba(147,51,234,40); color: white; }
QMenu {
    background: rgba(14,7,35,250); border: 1px solid rgba(255,255,255,12);
    border-radius: 14px; padding: 6px; color: white;
}
QMenu::item { padding: 8px 22px; border-radius: 8px; font-size:13px; }
QMenu::item:selected { background: rgba(147,51,234,45); }
QMenu::separator { height:1px; background:rgba(255,255,255,10); margin:5px 10px; }

QStatusBar { background:rgba(4,2,12,210); color:rgba(255,255,255,70); font-size:11px; }

QDialog, QInputDialog { background: rgba(12,6,30,252); }
QLabel { color: white; }
QLineEdit {
    background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,18);
    border-radius: 10px; padding: 8px 16px; color: white;
}
QLineEdit:focus { border-color: rgba(147,51,234,160); background: rgba(147,51,234,8); }
QComboBox {
    background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,15);
    border-radius: 10px; padding: 6px 14px; color: white;
}
QComboBox QAbstractItemView {
    background: rgba(14,7,35,250); color: white; border-radius: 10px;
    selection-background-color: rgba(147,51,234,50);
}
QToolTip {
    background: rgba(14,7,35,245); border: 1px solid rgba(255,255,255,15);
    border-radius: 8px; color: white; padding: 6px 12px;
}
QScrollArea { background: transparent; border: none; }
QFrame { background: transparent; }
QPushButton:flat { background: transparent; border: none; }
"""
