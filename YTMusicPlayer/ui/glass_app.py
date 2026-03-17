"""
ui/glass_app.py
───────────────
Single-canvas approach: one QWidget paints EVERYTHING (lava lamp + glass panels).
Interactive widgets (lists, inputs, buttons) float on top with WA_NoSystemBackground.
This is the only reliable way to get true glassmorphism in PyQt5 on Windows.
"""
import math, random, os, threading, time
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QApplication, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QSlider, QScrollArea, QVBoxLayout,
    QHBoxLayout, QAbstractItemView, QMenu, QAction, QSizePolicy,
    QInputDialog, QMessageBox, QShortcut, QStatusBar, QFrame,
)
from PyQt5.QtCore import (
    Qt, QTimer, QPointF, QRectF, pyqtSignal, pyqtSlot,
    QSettings, QSize, QPoint,
)
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen, QPixmap,
    QLinearGradient, QRadialGradient, QFont, QFontMetrics,
    QConicalGradient,
)
import requests


# ══════════════════════════════════════════════════════════════════════════════
#  LAVA LAMP ENGINE
# ══════════════════════════════════════════════════════════════════════════════
class Orb:
    COLORS = [
        (130,20,220,190),(200,20,140,170),(20,60,200,170),
        (180,60,10,160),(100,10,180,170),(220,50,80,160),
        (40,100,220,150),(160,20,200,170),
    ]
    def __init__(self,w,h,i):
        self.w=w; self.h=h; c=self.COLORS[i%len(self.COLORS)]
        self.r,self.g,self.b,self.a=c
        self.x=random.uniform(.15,.85)*w; self.y=random.uniform(.15,.85)*h
        s=random.uniform(.15,.4); ang=random.uniform(0,6.28)
        self.vx=math.cos(ang)*s; self.vy=math.sin(ang)*s
        self.br=random.uniform(.16,.30)*min(w,h); self.ra=self.br
        self.t=random.uniform(0,200); self.ps=random.uniform(.005,.015)
        self.pp=random.uniform(0,6.28)
        self.wf=[random.uniform(1.5,4.5) for _ in range(5)]
        self.wa=[random.uniform(.05,.14)*self.br for _ in range(5)]
        self.wp=[random.uniform(0,6.28) for _ in range(5)]
        self.ws=[random.uniform(.007,.022) for _ in range(5)]
    def update(self):
        self.t+=1; self.x+=self.vx; self.y+=self.vy
        pad=self.br*.9
        if self.x<pad or self.x>self.w-pad: self.vx*=-1; self.x=max(pad,min(self.w-pad,self.x))
        if self.y<pad or self.y>self.h-pad: self.vy*=-1; self.y=max(pad,min(self.h-pad,self.y))
        self.ra=self.br*(1+.12*math.sin(self.t*self.ps+self.pp))
        for i in range(5): self.wp[i]+=self.ws[i]
    def path(self):
        N=48; pts=[]
        for i in range(N):
            th=2*math.pi*i/N; r=self.ra
            for f,a,p in zip(self.wf,self.wa,self.wp): r+=a*math.sin(f*th+p)
            pts.append(QPointF(self.x+r*math.cos(th),self.y+r*math.sin(th)))
        pa=QPainterPath(); pa.moveTo(pts[0])
        for i in range(N):
            p0=pts[i]; p1=pts[(i+1)%N]; p2=pts[(i+2)%N]; pm=pts[(i-1)%N]
            pa.cubicTo(p0.x()+(p1.x()-pm.x())/6,p0.y()+(p1.y()-pm.y())/6,
                       p1.x()-(p2.x()-p0.x())/6,p1.y()-(p2.y()-p0.y())/6,p1.x(),p1.y())
        pa.closeSubpath(); return pa
    def grad(self):
        g=QRadialGradient(self.x,self.y,self.ra*1.6)
        g.setColorAt(0,  QColor(self.r,self.g,self.b,self.a))
        g.setColorAt(.4, QColor(self.r//2,self.g//2,self.b//2,self.a//2))
        g.setColorAt(1,  QColor(0,0,0,0))
        return g


class Spark:
    def __init__(self,w,h):
        self.w=w; self.h=h; self.reset()
    def reset(self):
        self.x=random.uniform(0,self.w); self.y=random.uniform(0,self.h)
        self.vx=random.uniform(-.25,.25); self.vy=random.uniform(-.45,-.08)
        self.rad=random.uniform(.8,2.5); self.life=1.0
        self.decay=random.uniform(.0015,.005)
        self.c=random.choice([(180,100,255),(255,100,190),(100,150,255),(255,165,80)])
        self.al=int(random.uniform(80,180))
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.life-=self.decay
        if self.life<=0 or self.y<0: self.reset(); self.life=1.0


# ══════════════════════════════════════════════════════════════════════════════
#  GLASS PANEL HELPERS  (drawn in the main paintEvent)
# ══════════════════════════════════════════════════════════════════════════════
def draw_glass_rect(p: QPainter, rect: QRectF, radius: float=16,
                    fill_alpha:int=35, border_alpha:int=45,
                    highlight:bool=True):
    """Draw a frosted-glass rounded rectangle."""
    p.save()
    # Fill
    p.setBrush(QBrush(QColor(12,5,30,fill_alpha)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(rect, radius, radius)
    # Top highlight edge
    if highlight:
        top=QLinearGradient(rect.left(),rect.top(),rect.left(),rect.top()+rect.height()*.3)
        top.setColorAt(0, QColor(255,255,255,22))
        top.setColorAt(1, QColor(255,255,255,0))
        p.setBrush(QBrush(top)); p.drawRoundedRect(rect,radius,radius)
    # Border
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255,255,255,border_alpha),1))
    p.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),radius,radius)
    p.restore()


def draw_glass_line(p:QPainter, x1,y1,x2,y2):
    p.save(); p.setPen(QPen(QColor(255,255,255,18),1)); p.drawLine(x1,y1,x2,y2); p.restore()


# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOM TRANSPARENT WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
def make_transparent(w:QWidget):
    w.setAttribute(Qt.WA_NoSystemBackground,True)
    w.setAttribute(Qt.WA_TranslucentBackground,True)
    w.setAutoFillBackground(False)


class GlassLineEdit(QLineEdit):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        make_transparent(self)
        self.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,12);
                border: 1px solid rgba(255,255,255,35);
                border-radius: 24px;
                padding: 10px 22px;
                color: white; font-size: 14px;
                selection-background-color: rgba(147,51,234,140);
            }
            QLineEdit:focus {
                background: rgba(147,51,234,18);
                border: 1px solid rgba(167,139,250,160);
            }
        """)


class GlassButton(QPushButton):
    def __init__(self,text,*a,**kw):
        super().__init__(text,*a,**kw)
        make_transparent(self)
        self.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,14);
                border: 1px solid rgba(255,255,255,35);
                border-radius: 24px;
                padding: 10px 24px;
                color: white; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(147,51,234,50);
                border-color: rgba(167,139,250,120);
            }
            QPushButton:pressed { background: rgba(147,51,234,80); }
            QPushButton:disabled { color: rgba(255,255,255,50); }
        """)


class GlassListWidget(QListWidget):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        make_transparent(self)
        self.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none; outline: none;
                padding: 0 6px;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 12px;
                color: rgba(255,255,255,170);
                padding: 0;
                margin: 1px 0;
            }
            QListWidget::item:hover {
                background: rgba(255,255,255,8);
                color: white;
            }
            QListWidget::item:selected {
                background: rgba(124,58,237,30);
                color: white;
                border: 1px solid rgba(147,51,234,50);
            }
            QScrollBar:vertical { background:transparent; width:4px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,22); border-radius:2px; min-height:20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)


class GlassNavButton(QPushButton):
    def __init__(self,text,*a,**kw):
        super().__init__(text,*a,**kw)
        self.setCheckable(True); self.setAutoExclusive(False); self.setFlat(True)
        make_transparent(self)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none; border-radius: 12px;
                padding: 10px 16px; text-align: left;
                color: rgba(255,255,255,130); font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,10);
                color: rgba(255,255,255,220);
            }
            QPushButton:checked {
                background: rgba(124,58,237,35);
                color: white; font-weight: 600;
                border: 1px solid rgba(147,51,234,55);
            }
        """)
        self.setMinimumHeight(42)


class CircleBtn(QPushButton):
    """Custom-painted circular button — fully transparent background."""
    def __init__(self,icon,sz=40,accent=False,parent=None):
        super().__init__(parent)
        self._icon=icon; self._sz=sz; self._accent=accent
        self._hov=False; self._active=False
        self.setFixedSize(sz,sz); self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        make_transparent(self)
    def setActive(self,v): self._active=v; self.update()
    def enterEvent(self,e): self._hov=True; self.update()
    def leaveEvent(self,e): self._hov=False; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect(); cx=r.width()/2; cy=r.height()/2
        if self._accent:
            g=QLinearGradient(0,0,r.width(),r.height())
            c1,c2 = ((168,85,247),(236,72,153)) if self._hov else ((124,58,237),(219,39,119))
            g.setColorAt(0,QColor(*c1)); g.setColorAt(1,QColor(*c2))
            p.setBrush(QBrush(g)); p.setPen(Qt.NoPen)
            p.drawEllipse(r.adjusted(2,2,-2,-2))
            # glow
            gw=QRadialGradient(cx,cy,cx+6)
            gw.setColorAt(0,QColor(147,51,234,0)); gw.setColorAt(.7,QColor(147,51,234,0))
            gw.setColorAt(1,QColor(147,51,234,60 if self._hov else 30))
            p.setBrush(QBrush(gw)); p.drawEllipse(r)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255,255,255,35),1))
            p.drawEllipse(r.adjusted(3,3,-3,-3))
        elif self._active:
            p.setBrush(QBrush(QColor(124,58,237,60)))
            p.setPen(QPen(QColor(167,139,250,130),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        elif self._hov:
            p.setBrush(QBrush(QColor(255,255,255,16)))
            p.setPen(QPen(QColor(255,255,255,35),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        else:
            p.setBrush(QBrush(QColor(255,255,255,10)))
            p.setPen(QPen(QColor(255,255,255,28),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        col = (QColor(255,255,255,240) if self._accent else
               QColor(167,139,250) if self._active else
               QColor(255,255,255,220) if self._hov else QColor(255,255,255,170))
        p.setPen(col)
        f=p.font(); f.setPointSize(max(8,int(self._sz*.28))); p.setFont(f)
        p.drawText(r,Qt.AlignCenter,self._icon)
        p.end()


class SeekBar(QWidget):
    valueChanged=pyqtSignal(float)
    pressed=pyqtSignal(); released=pyqtSignal(float)
    def __init__(self,p=None):
        super().__init__(p); self._v=0.0; self._drag=False
        self.setFixedHeight(18); self.setCursor(Qt.PointingHandCursor)
        make_transparent(self)
    def setValue(self,v): self._v=max(0.,min(1.,v)); self.update()
    def mousePressEvent(self,e): self._drag=True; self._set(e.x()); self.pressed.emit()
    def mouseMoveEvent(self,e):
        if self._drag: self._set(e.x())
    def mouseReleaseEvent(self,e): self._drag=False; self._set(e.x()); self.released.emit(self._v)
    def _set(self,x): pad=6; self._v=max(0.,min(1.,(x-pad)/max(1,self.width()-pad*2))); self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w=self.width(); cy=self.height()//2; pad=6; th=3
        p.setBrush(QBrush(QColor(255,255,255,22))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(pad,cy-th//2,w-pad*2,th,2,2)
        fw=int((w-pad*2)*self._v)
        if fw>0:
            g=QLinearGradient(pad,0,pad+fw,0)
            g.setColorAt(0,QColor(124,58,237)); g.setColorAt(1,QColor(219,39,119))
            p.setBrush(QBrush(g)); p.drawRoundedRect(pad,cy-th//2,fw,th,2,2)
        hx=pad+fw
        gw=QRadialGradient(hx,cy,12); gw.setColorAt(0,QColor(167,139,250,90)); gw.setColorAt(1,QColor(0,0,0,0))
        p.setBrush(QBrush(gw)); p.drawEllipse(hx-12,cy-12,24,24)
        p.setBrush(QBrush(Qt.white)); p.setPen(QPen(QColor(147,51,234,200),1.5))
        p.drawEllipse(hx-5,cy-5,10,10); p.end()


class ThumbLabel(QLabel):
    def __init__(self,sz=56):
        super().__init__(); self._pix=None; self.setFixedSize(sz,sz); make_transparent(self)
    def set_url(self,url):
        threading.Thread(target=self._fetch,args=(url,),daemon=True).start()
    def _fetch(self,url):
        try:
            r=requests.get(url,timeout=5); px=QPixmap(); px.loadFromData(r.content); self._pix=px
            from PyQt5.QtCore import QMetaObject,Qt as Q
            QMetaObject.invokeMethod(self,'_apply',Q.QueuedConnection)
        except: pass
    @pyqtSlot()
    def _apply(self): self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path=QPainterPath(); path.addRoundedRect(0,0,self.width(),self.height(),12,12)
        p.setClipPath(path)
        if self._pix:
            s=self._pix.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(0,0,s)
        else:
            g=QLinearGradient(0,0,self.width(),self.height())
            g.setColorAt(0,QColor(60,20,110)); g.setColorAt(1,QColor(30,10,70))
            p.fillPath(path,QBrush(g))
            p.setPen(QColor(180,120,255,200)); f=p.font(); f.setPointSize(22); p.setFont(f)
            p.drawText(self.rect(),Qt.AlignCenter,"♪")
        p.setClipping(False); p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255,255,255,30),1))
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),12,12)
        p.end()


class MiniThumb(QLabel):
    def __init__(self):
        super().__init__(); self._pix=None; self.setFixedSize(46,34); make_transparent(self)
    def set_url(self,url):
        threading.Thread(target=self._fetch,args=(url,),daemon=True).start()
    def _fetch(self,url):
        try:
            r=requests.get(url,timeout=4); px=QPixmap(); px.loadFromData(r.content); self._pix=px
            from PyQt5.QtCore import QMetaObject,Qt as Q
            QMetaObject.invokeMethod(self,'_apply',Q.QueuedConnection)
        except: pass
    @pyqtSlot()
    def _apply(self): self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path=QPainterPath(); path.addRoundedRect(0,0,self.width(),self.height(),6,6)
        p.setClipPath(path)
        if self._pix:
            s=self._pix.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(0,0,s)
        else:
            p.fillPath(path,QBrush(QColor(50,20,90)))
            p.setPen(QColor(160,100,220,150)); p.drawText(self.rect(),Qt.AlignCenter,"♪")
        p.end()


class TrackRow(QWidget):
    def __init__(self,data,idx,parent=None):
        super().__init__(parent); self.data=data; self.idx=idx; self._hi=False
        make_transparent(self); self._build()
    def _build(self):
        lay=QHBoxLayout(self); lay.setContentsMargins(10,7,16,7); lay.setSpacing(12)
        n=QLabel(str(self.idx+1)); n.setFixedWidth(28)
        n.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        n.setStyleSheet("color:rgba(255,255,255,55);font-size:11px;"); lay.addWidget(n)
        self._thumb=MiniThumb(); url=self.data.get("thumbnail","")
        if url: self._thumb.set_url(url)
        lay.addWidget(self._thumb)
        info=QVBoxLayout(); info.setSpacing(2); info.setContentsMargins(0,0,0,0)
        title=self.data.get("title","Unknown"); artist=self.data.get("uploader") or self.data.get("channel","")
        tl=QLabel((title[:62]+"…") if len(title)>62 else title)
        tl.setStyleSheet("color:rgba(255,255,255,215);font-size:13px;font-weight:500;background:transparent;")
        al=QLabel(artist[:50]); al.setStyleSheet("color:rgba(255,255,255,110);font-size:11px;background:transparent;")
        info.addWidget(tl); info.addWidget(al); lay.addLayout(info,1)
        dur=int(self.data.get("duration") or 0); m,s=divmod(dur,60); h,m=divmod(m,60)
        ds=f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        dl=QLabel(ds); dl.setStyleSheet("color:rgba(255,255,255,90);font-size:12px;background:transparent;")
        dl.setFixedWidth(48); dl.setAlignment(Qt.AlignRight|Qt.AlignVCenter); lay.addWidget(dl)
    def set_highlight(self,on): self._hi=on; self.update()
    def paintEvent(self,e):
        if self._hi:
            p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            g=QLinearGradient(0,0,self.width(),0)
            g.setColorAt(0,QColor(124,58,237,40)); g.setColorAt(.6,QColor(219,39,119,20)); g.setColorAt(1,QColor(0,0,0,0))
            p.setBrush(QBrush(g)); p.setPen(QPen(QColor(147,51,234,45),1))
            p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),10,10); p.end()
        super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CANVAS  — single widget, paints lava lamp + all glass panels
# ══════════════════════════════════════════════════════════════════════════════
class GlassCanvas(QWidget):
    """
    One widget that:
      1. Animates and draws the lava lamp background
      2. Draws all glass panel overlays (sidebar, header, player bar)
      3. Hosts all interactive child widgets positioned absolutely
    """

    # Layout constants
    SIDEBAR_W   = 230
    PLAYERBAR_H = 100
    SEARCH_H    = 72
    HEADER_H    = 80

    # Signals forwarded to MainWindow
    search_submitted    = pyqtSignal(str)
    track_double_clicked= pyqtSignal(dict,int)
    add_to_queue        = pyqtSignal(dict)
    add_to_playlist     = pyqtSignal(dict)
    like_track_sig      = pyqtSignal(dict)
    nav_changed         = pyqtSignal(str)
    new_playlist_sig    = pyqtSignal()
    play_pause_sig      = pyqtSignal()
    prev_sig            = pyqtSignal()
    next_sig            = pyqtSignal()
    stop_sig            = pyqtSignal()
    seek_sig            = pyqtSignal(int)
    volume_sig          = pyqtSignal(int)
    like_current_sig    = pyqtSignal()
    loop_sig            = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        make_transparent(self)

        # Lava lamp state
        self._orbs:list  = []
        self._sparks:list= []
        self._W = self._H = 0

        # App state
        self._tracks:list    = []
        self._cur_track      = -1
        self._nav_active     = "home"
        self._pl_btns:dict   = {}
        self._dur_ms         = 0
        self._seeking        = False
        self._liked          = False
        self._looping        = False
        self._section_title  = "Discover"
        self._section_sub    = "Popular tracks right now"

        self._build_widgets()

        # Animation timer
        self._anim=QTimer(self); self._anim.timeout.connect(self._tick)
        self._anim.start(33)  # ~30fps

    # ── Widget Construction ───────────────────────────────────────────────────
    def _build_widgets(self):
        # Search bar + button
        self._search_input = GlassLineEdit(self)
        self._search_input.setPlaceholderText("Search songs, artists, albums…")
        self._search_input.returnPressed.connect(self._on_search)

        self._search_btn = GlassButton("Search", self)
        self._search_btn.setFixedWidth(100)
        self._search_btn.clicked.connect(self._on_search)

        # Nav buttons
        nav_defs = [("search","🔍  Search"),("home","🏠  Home"),
                    ("liked","♥  Liked Songs"),("history","🕐  History")]
        self._nav_btns:dict = {}
        for sid, label in nav_defs:
            btn = GlassNavButton(label, self)
            btn.clicked.connect(lambda _,s=sid: self._on_nav(s))
            self._nav_btns[sid] = btn

        self._new_pl_btn = QPushButton("  ＋  New Playlist", self)
        self._new_pl_btn.setFlat(True); make_transparent(self._new_pl_btn)
        self._new_pl_btn.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:10px;
                padding:8px 16px;text-align:left;color:rgba(167,139,250,200);font-size:12px;}
            QPushButton:hover{background:rgba(124,58,237,20);color:#c4b5fd;}
        """)
        self._new_pl_btn.clicked.connect(self.new_playlist_sig)
        self._new_pl_btn.setMinimumHeight(36)

        # Track list
        self._list = GlassListWidget(self)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_dbl)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_ctx)

        # Status label
        self._status_lbl = QLabel(self)
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color:rgba(255,255,255,80);font-size:14px;background:transparent;")
        self._status_lbl.hide()

        # Player widgets
        self._thumb = ThumbLabel(60)
        self._thumb.setParent(self)
        self._title_lbl = QLabel("Nothing playing", self)
        self._title_lbl.setStyleSheet("color:white;font-size:14px;font-weight:600;background:transparent;")
        self._artist_lbl = QLabel("—", self)
        self._artist_lbl.setStyleSheet("color:rgba(255,255,255,120);font-size:11px;background:transparent;")

        self._like_btn  = CircleBtn("♡",32,parent=self); self._like_btn.clicked.connect(self.like_current_sig)
        self._loop_btn  = CircleBtn("⟳",36,parent=self); self._loop_btn.clicked.connect(self._on_loop)
        self._prev_btn  = CircleBtn("⏮",42,parent=self); self._prev_btn.clicked.connect(self.prev_sig)
        self._play_btn  = CircleBtn("▶",58,accent=True,parent=self); self._play_btn.clicked.connect(self.play_pause_sig)
        self._next_btn  = CircleBtn("⏭",42,parent=self); self._next_btn.clicked.connect(self.next_sig)
        self._stop_btn  = CircleBtn("⏹",36,parent=self); self._stop_btn.clicked.connect(self.stop_sig)

        self._pos_lbl = QLabel("0:00",self)
        self._pos_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;")
        self._dur_lbl = QLabel("0:00",self)
        self._dur_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;")
        self._seek_bar = SeekBar(self)
        self._seek_bar.pressed.connect(lambda:setattr(self,"_seeking",True))
        self._seek_bar.released.connect(self._on_seek)

        self._vol_lbl = QLabel("🔊",self)
        self._vol_lbl.setStyleSheet("font-size:14px;color:rgba(255,255,255,130);background:transparent;")
        self._vol_slider = QSlider(Qt.Horizontal,self)
        self._vol_slider.setRange(0,100); self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(88); self._vol_slider.setCursor(Qt.PointingHandCursor)
        make_transparent(self._vol_slider)
        self._vol_slider.setStyleSheet("""
            QSlider::groove:horizontal{background:rgba(255,255,255,20);height:3px;border-radius:2px;}
            QSlider::sub-page:horizontal{background:rgba(167,139,250,190);border-radius:2px;}
            QSlider::handle:horizontal{background:white;border:2px solid rgba(124,58,237,200);
                width:10px;height:10px;margin:-3px 0;border-radius:5px;}
        """)
        self._vol_slider.valueChanged.connect(self.volume_sig)

        # Nav active state
        self._nav_btns["home"].setChecked(True)

        # Pl scroll area for sidebar playlists
        self._pl_scroll = QScrollArea(self)
        self._pl_scroll.setWidgetResizable(True)
        self._pl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pl_scroll.setStyleSheet("background:transparent;border:none;")
        make_transparent(self._pl_scroll)
        self._pl_container = QWidget()
        make_transparent(self._pl_container)
        self._pl_container.setStyleSheet("background:transparent;")
        self._pl_vlay = QVBoxLayout(self._pl_container)
        self._pl_vlay.setContentsMargins(0,0,0,0); self._pl_vlay.setSpacing(2)
        self._pl_vlay.addStretch()
        self._pl_scroll.setWidget(self._pl_container)

        # Settings button
        self._settings_btn = GlassNavButton("⚙  Settings", self)
        self._settings_btn.clicked.connect(lambda:self._on_nav("settings"))

    # ── Layout ────────────────────────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        w=self.width(); h=self.height()
        sw=self.SIDEBAR_W; ph=self.PLAYERBAR_H
        sh=self.SEARCH_H; hh=self.HEADER_H
        cx=sw; cw=w-sw  # content area

        # Re-init lava lamp
        self._W=w; self._H=h
        self._orbs=[Orb(w,h,i) for i in range(9)]
        self._sparks=[Spark(w,h) for _ in range(70)]

        # Sidebar nav buttons
        by=60  # below title
        for btn in self._nav_btns.values():
            btn.setGeometry(10,by,sw-20,42); by+=46
        by+=8  # library label gap
        by+=22  # "LIBRARY" label height
        self._new_pl_btn.setGeometry(10,by,sw-20,36); by+=40
        self._pl_scroll.setGeometry(10,by,sw-20,h-ph-by-50)
        self._settings_btn.setGeometry(10,h-ph-48,sw-20,42)

        # Search bar
        self._search_input.setGeometry(cx+20,12,cw-160,48)
        self._search_btn.setGeometry(cx+cw-120,12,100,48)

        # Track list
        list_top = sh+hh
        self._list.setGeometry(cx, list_top, cw, h-ph-list_top)
        self._status_lbl.setGeometry(cx, list_top, cw, h-ph-list_top)

        # Player bar widgets
        py = h-ph  # top of player bar
        # Thumb
        self._thumb.setGeometry(20, py+22, 60, 60)
        # Title/artist
        self._title_lbl.setGeometry(90, py+26, 180, 22)
        self._artist_lbl.setGeometry(90, py+52, 180, 18)
        # Like
        self._like_btn.setGeometry(278, py+34, 32, 32)

        # Transport buttons — centre of player bar
        mid=w//2; bw=58; gap=10
        total=(32+gap+42+gap+58+gap+42+gap+36)
        bx=mid-total//2
        self._loop_btn.setGeometry(bx,py+20,36,36); bx+=36+gap
        self._prev_btn.setGeometry(bx,py+16,42,42); bx+=42+gap
        self._play_btn.setGeometry(bx,py+12,58,58); bx+=58+gap
        self._next_btn.setGeometry(bx,py+16,42,42); bx+=42+gap
        self._stop_btn.setGeometry(bx,py+20,36,36)

        # Seek bar
        self._pos_lbl.setGeometry(mid-380, py+68, 40, 20)
        self._seek_bar.setGeometry(mid-336, py+66, 672, 22)
        self._dur_lbl.setGeometry(mid+340, py+68, 40, 20)

        # Volume
        self._vol_lbl.setGeometry(w-140, py+38, 24, 24)
        self._vol_slider.setGeometry(w-112, py+40, 88, 20)

    # ── Animation ─────────────────────────────────────────────────────────────
    def _tick(self):
        for o in self._orbs: o.update()
        for s in self._sparks: s.update()
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w=self.width(); h=self.height()
        if w<1 or h<1: p.end(); return

        sw=self.SIDEBAR_W; ph=self.PLAYERBAR_H
        sh=self.SEARCH_H; hh=self.HEADER_H

        # ── 1. Deep background ────────────────────────────────────────────────
        bg=QLinearGradient(0,0,w,h)
        bg.setColorAt(0,QColor(7,3,18)); bg.setColorAt(.5,QColor(14,5,32)); bg.setColorAt(1,QColor(5,2,14))
        p.fillRect(0,0,w,h,bg)

        # Warm corner wash
        warm=QRadialGradient(w*.85,h*.75,h*.7)
        warm.setColorAt(0,QColor(180,55,10,55)); warm.setColorAt(1,QColor(0,0,0,0))
        p.fillRect(0,0,w,h,warm)

        # ── 2. Orbs (additive) ────────────────────────────────────────────────
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for o in self._orbs:
            p.setBrush(QBrush(o.grad())); p.setPen(Qt.NoPen); p.drawPath(o.path())

        # Sparks
        for s in self._sparks:
            al=int(s.al*s.life); r,g,b=s.c
            p.setBrush(QBrush(QColor(r,g,b,al))); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(s.x,s.y),s.rad,s.rad)

        # ── 3. Vignette ───────────────────────────────────────────────────────
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        vig=QRadialGradient(w/2,h/2,max(w,h)*.72)
        vig.setColorAt(.3,QColor(0,0,0,0)); vig.setColorAt(.75,QColor(0,0,0,70)); vig.setColorAt(1,QColor(0,0,0,190))
        p.fillRect(0,0,w,h,vig)

        # ── 4. SIDEBAR glass panel ────────────────────────────────────────────
        draw_glass_rect(p, QRectF(0,0,sw,h-ph), 0, fill_alpha=28, border_alpha=0, highlight=False)
        # Right edge gleam
        re=QLinearGradient(sw-1,0,sw+1,0)
        re.setColorAt(0,QColor(255,255,255,35)); re.setColorAt(1,QColor(255,255,255,0))
        p.fillRect(sw-1,0,2,h,re)

        # App title
        p.setPen(QColor(255,255,255,230)); f=QFont("Segoe UI",15,QFont.Bold); p.setFont(f)
        p.drawText(QRectF(20,22,sw-24,36),Qt.AlignVCenter,"▶  YTMusicPlayer")

        # Nav separator after nav buttons
        nav_end_y = 60 + 4*46 + 8
        p.setPen(QPen(QColor(255,255,255,18),1))
        p.drawLine(14,nav_end_y,sw-14,nav_end_y)

        # "LIBRARY" label
        p.setPen(QColor(255,255,255,60))
        f2=QFont("Segoe UI",9,QFont.Bold); f2.setLetterSpacing(QFont.AbsoluteSpacing,2); p.setFont(f2)
        p.drawText(QRectF(20,nav_end_y+8,sw-24,20),Qt.AlignVCenter,"LIBRARY")

        # Bottom separator
        p.setPen(QPen(QColor(255,255,255,18),1))
        p.drawLine(14,h-ph-54,sw-14,h-ph-54)

        # ── 5. CONTENT: search bar glass panel ────────────────────────────────
        draw_glass_rect(p,QRectF(sw,0,w-sw,sh),0,fill_alpha=22,border_alpha=0,highlight=False)
        draw_glass_line(p,sw,sh,w,sh)

        # ── 6. CONTENT: section header ────────────────────────────────────────
        # Subtle header gradient strip
        hg=QLinearGradient(sw,sh,w,sh+hh)
        hg.setColorAt(0,QColor(80,20,160,18)); hg.setColorAt(1,QColor(0,0,0,0))
        p.fillRect(sw,sh,w-sw,hh,hg)
        p.setPen(QColor(255,255,255,230))
        f3=QFont("Segoe UI",26,QFont.Bold); p.setFont(f3)
        p.drawText(QRectF(sw+24,sh+12,w-sw-48,40),Qt.AlignVCenter,self._section_title)
        p.setPen(QColor(255,255,255,90)); f4=QFont("Segoe UI",11); p.setFont(f4)
        p.drawText(QRectF(sw+24,sh+52,w-sw-48,24),Qt.AlignVCenter,self._section_sub)
        draw_glass_line(p,sw,sh+hh,w,sh+hh)

        # ── 7. PLAYER BAR glass panel ─────────────────────────────────────────
        py=h-ph
        # Blurred-glass feel via layered semi-transparent rects
        bar_g=QLinearGradient(0,py,0,h)
        bar_g.setColorAt(0,QColor(10,4,28,130)); bar_g.setColorAt(1,QColor(6,2,18,160))
        p.fillRect(0,py,w,ph,bar_g)
        # Top border glow
        glow_line=QLinearGradient(0,py,w,py)
        glow_line.setColorAt(0,QColor(124,58,237,0))
        glow_line.setColorAt(.4,QColor(167,139,250,60))
        glow_line.setColorAt(.6,QColor(219,39,119,50))
        glow_line.setColorAt(1,QColor(219,39,119,0))
        p.fillRect(0,py,w,2,glow_line)

        # Divider between sidebar and content in player bar
        p.setPen(QPen(QColor(255,255,255,15),1)); p.drawLine(sw,py,sw,h)

        p.end()

    # ── Public API (called by MainWindow) ─────────────────────────────────────
    def set_tracks(self, tracks:list):
        self._tracks=tracks; self._list.clear(); self._status_lbl.hide()
        for i,t in enumerate(tracks):
            item=QListWidgetItem(self._list)
            row=TrackRow(t,i); item.setSizeHint(QSize(0,60))
            self._list.addItem(item); self._list.setItemWidget(item,row)

    def show_status(self,msg:str):
        self._status_lbl.setText(msg); self._status_lbl.show(); self._list.clear()

    def set_section(self,title:str,sub:str):
        self._section_title=title; self._section_sub=sub; self.update()

    def set_current_index(self,idx:int):
        prev=self._cur_track; self._cur_track=idx
        for i in (prev,idx):
            if 0<=i<self._list.count():
                w=self._list.itemWidget(self._list.item(i))
                if isinstance(w,TrackRow): w.set_highlight(i==idx)
        if 0<=idx<self._list.count():
            self._list.scrollToItem(self._list.item(idx),QAbstractItemView.PositionAtCenter)

    def set_track_info(self,title,artist):
        t=(title[:26]+"…") if len(title)>26 else title
        self._title_lbl.setText(t); self._artist_lbl.setText(artist)

    def set_thumbnail(self,url): self._thumb.set_url(url)

    def set_playing(self,playing):
        self._play_btn._icon="⏸" if playing else "▶"; self._play_btn.update()

    def set_position(self,ms:int):
        if self._seeking: return
        s=ms//1000; m,s=divmod(s,60)
        self._pos_lbl.setText(f"{m}:{s:02d}")
        if self._dur_ms>0: self._seek_bar.setValue(ms/self._dur_ms)

    def set_duration(self,ms:int):
        self._dur_ms=ms; s=ms//1000; m,s=divmod(s,60)
        self._dur_lbl.setText(f"{m}:{s:02d}")

    def set_liked(self,liked:bool):
        self._liked=liked; self._like_btn._icon="♥" if liked else "♡"
        self._like_btn._active=liked; self._like_btn.update()

    def get_volume(self)->int: return self._vol_slider.value()

    def focus_search(self): self._search_input.setFocus()

    def update_playlists(self,playlists:dict):
        for btn in self._pl_btns.values(): btn.setParent(None)
        self._pl_btns.clear()
        item=self._pl_vlay.takeAt(self._pl_vlay.count()-1)
        for pid,info in playlists.items():
            btn=GlassNavButton(f"  📋  {info.get('name','Untitled')}",self._pl_container)
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda _,p=pid:self._on_nav(f"playlist:{p}"))
            self._pl_vlay.addWidget(btn); self._pl_btns[pid]=btn
        self._pl_vlay.addStretch()

    def set_search_loading(self,on:bool):
        self._search_btn.setText("…" if on else "Search")
        self._search_btn.setEnabled(not on); self._search_input.setEnabled(not on)

    # ── Internal handlers ─────────────────────────────────────────────────────
    def _on_search(self):
        q=self._search_input.text().strip()
        if q: self.search_submitted.emit(q)

    def _on_nav(self,section:str):
        self._nav_active=section
        for sid,btn in self._nav_btns.items(): btn.setChecked(sid==section)
        for pid,btn in self._pl_btns.items(): btn.setChecked(f"playlist:{pid}"==section)
        self.nav_changed.emit(section)

    def _on_dbl(self,item):
        r=self._list.row(item)
        if 0<=r<len(self._tracks): self.track_double_clicked.emit(self._tracks[r],r)

    def _on_ctx(self,pos):
        item=self._list.itemAt(pos)
        if not item: return
        r=self._list.row(item)
        if r<0 or r>=len(self._tracks): return
        t=self._tracks[r]
        menu=QMenu(self)
        menu.setStyleSheet("""
            QMenu{background:rgba(14,7,35,252);border:1px solid rgba(255,255,255,15);
                  border-radius:14px;padding:6px;color:white;}
            QMenu::item{padding:9px 22px;border-radius:8px;font-size:13px;}
            QMenu::item:selected{background:rgba(124,58,237,55);}
        """)
        for lbl,fn in[("▶  Play now",lambda:self.track_double_clicked.emit(t,r)),
                      ("➕  Add to queue",lambda:self.add_to_queue.emit(t)),
                      ("♥  Like",lambda:self.like_track_sig.emit(t)),
                      ("📋  Add to playlist",lambda:self.add_to_playlist.emit(t))]:
            a=QAction(lbl,self); a.triggered.connect(fn); menu.addAction(a)
        menu.exec_(self._list.mapToGlobal(pos))

    def _on_seek(self,ratio:float):
        self._seeking=False
        if self._dur_ms>0: self.seek_sig.emit(int(ratio*self._dur_ms))

    def _on_loop(self):
        self._looping=not self._looping
        self._loop_btn.setActive(self._looping); self.loop_sig.emit(self._looping)
