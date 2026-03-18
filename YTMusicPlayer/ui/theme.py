"""ui/theme.py — Premium glassmorphism stylesheet."""

ACCENT_PURPLE = "#7C3AED"
ACCENT_PINK   = "#DB2777"
ACCENT_BLUE   = "#2563EB"
TEXT_MUTED    = "rgba(255,255,255,120)"
GLASS_BG      = "rgba(15,8,35,0.85)"
GLASS_BORDER  = "rgba(255,255,255,18)"

APP_STYLESHEET = """
* {
    color: #FFFFFF;
    font-family: "Segoe UI", "SF Pro Display", Arial, sans-serif;
    font-size: 13px;
    border: none; outline: none; margin: 0; padding: 0;
    selection-background-color: rgba(147,51,234,120);
}
QMainWindow { background: #060210; }
QWidget     { background: transparent; }
QScrollBar:vertical   { background:transparent; width:4px; margin:0; }
QScrollBar::handle:vertical { background:rgba(255,255,255,18); border-radius:2px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:4px; }
QScrollBar::handle:horizontal { background:rgba(255,255,255,18); border-radius:2px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
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
QStatusBar { background:rgba(4,2,12,210); color:rgba(255,255,255,70); font-size:11px; }
QDialog, QInputDialog { background: rgba(12,6,30,252); }
QLabel { color: white; }
QLineEdit {
    background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,18);
    border-radius: 10px; padding: 8px 16px; color: white;
}
QLineEdit:focus { border-color: rgba(147,51,234,160); background: rgba(147,51,234,8); }
QToolTip {
    background: rgba(14,7,35,245); border: 1px solid rgba(255,255,255,15);
    border-radius: 8px; color: white; padding: 6px 12px;
}
QScrollArea { background: transparent; border: none; }
QFrame { background: transparent; }
QPushButton:flat { background: transparent; border: none; }
"""
