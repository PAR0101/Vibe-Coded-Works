"""
ui/glass_app.py  ─  v5
────────────────────────
Fixes & Changes
───────────────
* Thumbnails  – replaced signal-across-thread approach with a thread-safe
  queue drained by a QTimer on the main thread; QPixmap is always built on
  the GUI thread.  Fallback YouTube thumbnail URL from video ID.
* Related tab  – cached; populated as soon as smart-autoplay results arrive
  even when the overlay is closed.
* Removed: Add-to-Queue button/signal, Settings button.
* Added: Add-to-Playlist button in the player bar.
* Playbar  – entire bar is clickable to open/close the expanded view.
* Expanded overlay  – shows skeleton rows while the queue/related is loading.
* Icons  – CircleBtn sizes increased ~15 %.
* PlaylistPickerModal  – glass modal replacing QInputDialog for playlist ops.
"""

import math, random, threading, queue as _queue
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QLineEdit, QPushButton,
    QLabel, QSlider, QScrollArea, QVBoxLayout, QHBoxLayout,
    QAbstractItemView, QMenu, QAction, QFrame, QDialog, QStackedWidget,
)
from PyQt5.QtCore import (
    Qt, QTimer, QPointF, QRectF, pyqtSignal, pyqtSlot, QSize,
)
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen, QPixmap,
    QLinearGradient, QRadialGradient, QFont,
)
import requests

# ── dict / TrackInfo normaliser ───────────────────────────────────────────────
def _as_dict(t) -> dict:
    if isinstance(t, dict): return t
    return {"id": getattr(t,"id",""), "title": getattr(t,"title","Unknown"),
            "uploader": getattr(t,"channel",""), "duration": getattr(t,"duration",0),
            "thumbnail": getattr(t,"thumbnail",""), "webpage_url": getattr(t,"webpage_url","")}

def _thumb_url(d: dict) -> str:
    """Return thumbnail URL, falling back to the standard ytimg URL from the video id."""
    u = d.get("thumbnail","")
    if u: return u
    vid = d.get("id","")
    return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ""


# ══════════════════════════════════════════════════════════════════════════════
#  THUMBNAIL SYSTEM  – queue-drain approach (100 % thread-safe)
# ══════════════════════════════════════════════════════════════════════════════
_PIX_CACHE:   dict       = {}            # url → QPixmap  (GUI thread only)
_FETCH_Q:     _queue.Queue = _queue.Queue()  # background → main thread
_IN_FLIGHT:   set        = set()         # urls currently being downloaded

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")


def _fetch_thumb_worker(url: str):
    """Daemon thread: download bytes, push to queue. Zero Qt calls."""
    try:
        r = requests.get(url, timeout=7, headers={"User-Agent": _UA})
        if r.ok and r.content:
            _FETCH_Q.put((url, r.content))
    except Exception:
        pass
    finally:
        _IN_FLIGHT.discard(url)


def request_thumb(url: str):
    if not url or url in _PIX_CACHE or url in _IN_FLIGHT:
        return
    _IN_FLIGHT.add(url)
    threading.Thread(target=_fetch_thumb_worker, args=(url,), daemon=True).start()


# Singleton drain timer – created once the QApplication exists
class _DrainTimer(QWidget):           # QWidget so it lives on the GUI thread
    _inst: Optional["_DrainTimer"] = None

    @classmethod
    def ensure(cls):
        if cls._inst is None:
            cls._inst = cls()

    def __init__(self):
        super().__init__()
        self._subs: list[QWidget] = []      # weakly-referenced thumb widgets
        t = QTimer(self); t.timeout.connect(self._drain); t.start(40)

    def subscribe(self, w: QWidget):
        self._subs.append(w)

    def _drain(self):
        """Called every 40 ms on the GUI thread – build QPixmaps here."""
        changed: list[str] = []
        try:
            while True:
                url, data = _FETCH_Q.get_nowait()
                px = QPixmap()
                if px.loadFromData(data) and not px.isNull():
                    _PIX_CACHE[url] = px
                    changed.append(url)
        except _queue.Empty:
            pass
        if not changed:
            return
        alive = []
        for w in self._subs:
            try:
                w._on_thumb_ready(changed)   # type: ignore[attr-defined]
                alive.append(w)
            except RuntimeError:
                pass   # widget was deleted
        self._subs = alive


# ══════════════════════════════════════════════════════════════════════════════
#  LAVA LAMP
# ══════════════════════════════════════════════════════════════════════════════
class Orb:
    COLORS = [(130,20,220,190),(200,20,140,170),(20,60,200,170),(180,60,10,160),
              (100,10,180,170),(220,50,80,160),(40,100,220,150),(160,20,200,170)]
    def __init__(self,w,h,i):
        self.w=w; self.h=h; c=self.COLORS[i%len(self.COLORS)]
        self.r,self.g,self.b,self.a=c
        self.x=random.uniform(.15,.85)*w; self.y=random.uniform(.15,.85)*h
        s=random.uniform(.15,.4); ang=random.uniform(0,6.28)
        self.vx=math.cos(ang)*s; self.vy=math.sin(ang)*s
        self.br=random.uniform(.16,.30)*min(w,h); self.ra=self.br
        self.t=random.uniform(0,200); self.ps=random.uniform(.005,.015); self.pp=random.uniform(0,6.28)
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
        g.setColorAt(0,QColor(self.r,self.g,self.b,self.a))
        g.setColorAt(.4,QColor(self.r//2,self.g//2,self.b//2,self.a//2))
        g.setColorAt(1,QColor(0,0,0,0)); return g

class Spark:
    def __init__(self,w,h): self.w=w; self.h=h; self.reset()
    def reset(self):
        self.x=random.uniform(0,self.w); self.y=random.uniform(0,self.h)
        self.vx=random.uniform(-.25,.25); self.vy=random.uniform(-.45,-.08)
        self.rad=random.uniform(.8,2.5); self.life=1.0; self.decay=random.uniform(.0015,.005)
        self.c=random.choice([(180,100,255),(255,100,190),(100,150,255),(255,165,80)])
        self.al=int(random.uniform(80,180))
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.life-=self.decay
        if self.life<=0 or self.y<0: self.reset(); self.life=1.0


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def make_transparent(w: QWidget):
    w.setAttribute(Qt.WA_NoSystemBackground,True)
    w.setAttribute(Qt.WA_TranslucentBackground,True)
    w.setAutoFillBackground(False)

def draw_glass_rect(p:QPainter,rect:QRectF,radius:float=16,fill_alpha:int=35,
                    border_alpha:int=45,highlight:bool=True):
    p.save()
    p.setBrush(QBrush(QColor(12,5,30,fill_alpha))); p.setPen(Qt.NoPen)
    p.drawRoundedRect(rect,radius,radius)
    if highlight:
        top=QLinearGradient(rect.left(),rect.top(),rect.left(),rect.top()+rect.height()*.3)
        top.setColorAt(0,QColor(255,255,255,22)); top.setColorAt(1,QColor(255,255,255,0))
        p.setBrush(QBrush(top)); p.drawRoundedRect(rect,radius,radius)
    p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255,255,255,border_alpha),1))
    p.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),radius,radius); p.restore()

def draw_glass_line(p:QPainter,x1,y1,x2,y2):
    p.save(); p.setPen(QPen(QColor(255,255,255,18),1)); p.drawLine(x1,y1,x2,y2); p.restore()


# ══════════════════════════════════════════════════════════════════════════════
#  THUMBNAIL WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
class MiniThumb(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix: Optional[QPixmap] = None
        self._url = ""
        self.setFixedSize(46,34); make_transparent(self)
        _DrainTimer.ensure(); _DrainTimer._inst.subscribe(self)  # type: ignore

    def set_url(self, url: str):
        if not url or url == self._url: return
        self._url = url
        if url in _PIX_CACHE: self._pix = _PIX_CACHE[url]; self.update(); return
        request_thumb(url)

    def _on_thumb_ready(self, urls: list):
        if self._url in urls: self._pix = _PIX_CACHE.get(self._url); self.update()

    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path=QPainterPath(); path.addRoundedRect(0,0,self.width(),self.height(),6,6)
        p.setClipPath(path)
        if self._pix and not self._pix.isNull():
            s=self._pix.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(0,0,s)
        else:
            p.fillPath(path,QBrush(QColor(50,20,90,210)))
            p.setPen(QColor(160,100,220,160)); f=p.font(); f.setPointSize(10); p.setFont(f)
            p.drawText(self.rect(),Qt.AlignCenter,"♪")
        p.end()


class ThumbLabel(QLabel):
    def __init__(self, sz:int=56, radius:int=12, parent=None):
        super().__init__(parent)
        self._pix: Optional[QPixmap] = None
        self._url = ""; self._r = radius
        self.setFixedSize(sz,sz); make_transparent(self)
        _DrainTimer.ensure(); _DrainTimer._inst.subscribe(self)  # type: ignore

    def set_url(self, url: str):
        if not url or url == self._url: return
        self._url = url
        if url in _PIX_CACHE: self._pix = _PIX_CACHE[url]; self.update(); return
        request_thumb(url)

    def _on_thumb_ready(self, urls: list):
        if self._url in urls: self._pix = _PIX_CACHE.get(self._url); self.update()

    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self._r; path=QPainterPath(); path.addRoundedRect(0,0,self.width(),self.height(),r,r)
        p.setClipPath(path)
        if self._pix and not self._pix.isNull():
            s=self._pix.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(0,0,s)
        else:
            g=QLinearGradient(0,0,self.width(),self.height())
            g.setColorAt(0,QColor(60,20,110)); g.setColorAt(1,QColor(30,10,70))
            p.fillPath(path,QBrush(g)); p.setPen(QColor(180,120,255,200))
            f=p.font(); f.setPointSize(int(self.width()*.28)); p.setFont(f)
            p.drawText(self.rect(),Qt.AlignCenter,"♪")
        p.setClipping(False); p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255,255,255,30),1))
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),r,r); p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  REUSABLE WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
class ClickableLabel(QLabel):
    clicked = pyqtSignal(str)
    def __init__(self,text="",parent=None):
        super().__init__(text,parent); self.setCursor(Qt.PointingHandCursor)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self.clicked.emit(self.text())
        super().mousePressEvent(e)


class GlassLineEdit(QLineEdit):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); make_transparent(self)
        self.setStyleSheet("""
            QLineEdit{background:rgba(255,255,255,12);border:1px solid rgba(255,255,255,35);
                border-radius:24px;padding:10px 22px;color:white;font-size:14px;
                selection-background-color:rgba(147,51,234,140);}
            QLineEdit:focus{background:rgba(147,51,234,18);border:1px solid rgba(167,139,250,160);}
        """)


class GlassButton(QPushButton):
    def __init__(self,text,*a,**kw):
        super().__init__(text,*a,**kw); make_transparent(self)
        self.setStyleSheet("""
            QPushButton{background:rgba(255,255,255,14);border:1px solid rgba(255,255,255,35);
                border-radius:24px;padding:10px 24px;color:white;font-size:13px;font-weight:600;}
            QPushButton:hover{background:rgba(147,51,234,50);border-color:rgba(167,139,250,120);}
            QPushButton:pressed{background:rgba(147,51,234,80);}
            QPushButton:disabled{color:rgba(255,255,255,50);}
        """)


class GlassListWidget(QListWidget):
    near_bottom = pyqtSignal()
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); make_transparent(self); self._cool=False
        self.verticalScrollBar().valueChanged.connect(self._chk)
        self.setStyleSheet("""
            QListWidget{background:transparent;border:none;outline:none;padding:0 6px;}
            QListWidget::item{background:transparent;border-radius:12px;padding:0;margin:1px 0;}
            QListWidget::item:hover{background:rgba(255,255,255,8);}
            QListWidget::item:selected{background:rgba(124,58,237,30);border:1px solid rgba(147,51,234,50);}
            QScrollBar:vertical{background:transparent;width:4px;}
            QScrollBar::handle:vertical{background:rgba(255,255,255,22);border-radius:2px;min-height:20px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)
    def _chk(self,v):
        sb=self.verticalScrollBar()
        if not self._cool and sb.maximum()>0 and v>=sb.maximum()*.82:
            self._cool=True; self.near_bottom.emit()
            QTimer.singleShot(2200,lambda:setattr(self,"_cool",False))
    def reset_cool(self): self._cool=False


class GlassNavButton(QPushButton):
    def __init__(self,text,*a,**kw):
        super().__init__(text,*a,**kw)
        self.setCheckable(True); self.setAutoExclusive(False); self.setFlat(True)
        make_transparent(self); self.setMinimumHeight(42)
        self.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:12px;
                padding:10px 16px;text-align:left;color:rgba(255,255,255,130);font-size:13px;}
            QPushButton:hover{background:rgba(255,255,255,10);color:rgba(255,255,255,220);}
            QPushButton:checked{background:rgba(124,58,237,35);color:white;font-weight:600;
                border:1px solid rgba(147,51,234,55);}
        """)


class CircleBtn(QPushButton):
    def __init__(self,icon,sz=46,accent=False,parent=None):
        super().__init__(parent)
        self._icon=icon; self._sz=sz; self._accent=accent; self._hov=False; self._active=False
        self.setFixedSize(sz,sz); self.setFlat(True); self.setCursor(Qt.PointingHandCursor)
        make_transparent(self)
    def setActive(self,v): self._active=v; self.update()
    def enterEvent(self,e): self._hov=True; self.update()
    def leaveEvent(self,e): self._hov=False; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect(); cx=r.width()/2; cy=r.height()/2
        if self._accent:
            g=QLinearGradient(0,0,r.width(),r.height())
            c1,c2=((168,85,247),(236,72,153)) if self._hov else ((124,58,237),(219,39,119))
            g.setColorAt(0,QColor(*c1)); g.setColorAt(1,QColor(*c2))
            p.setBrush(QBrush(g)); p.setPen(Qt.NoPen); p.drawEllipse(r.adjusted(2,2,-2,-2))
            gw=QRadialGradient(cx,cy,cx+6); gw.setColorAt(0,QColor(147,51,234,0))
            gw.setColorAt(.7,QColor(147,51,234,0)); gw.setColorAt(1,QColor(147,51,234,60 if self._hov else 30))
            p.setBrush(QBrush(gw)); p.drawEllipse(r)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255,255,255,35),1)); p.drawEllipse(r.adjusted(3,3,-3,-3))
        elif self._active:
            p.setBrush(QBrush(QColor(124,58,237,60))); p.setPen(QPen(QColor(167,139,250,130),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        elif self._hov:
            p.setBrush(QBrush(QColor(255,255,255,16))); p.setPen(QPen(QColor(255,255,255,35),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        else:
            p.setBrush(QBrush(QColor(255,255,255,10))); p.setPen(QPen(QColor(255,255,255,28),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        col=(QColor(255,255,255,240) if self._accent else QColor(167,139,250) if self._active
             else QColor(255,255,255,220) if self._hov else QColor(255,255,255,170))
        p.setPen(col); f=p.font(); f.setPointSize(max(9,int(self._sz*.30))); p.setFont(f)
        p.drawText(r,Qt.AlignCenter,self._icon); p.end()


class SeekBar(QWidget):
    pressed=pyqtSignal(); released=pyqtSignal(float)
    def __init__(self,parent=None):
        super().__init__(parent); self._v=0.0; self._drag=False
        self.setFixedHeight(18); self.setCursor(Qt.PointingHandCursor); make_transparent(self)
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
            g=QLinearGradient(pad,0,pad+fw,0); g.setColorAt(0,QColor(124,58,237)); g.setColorAt(1,QColor(219,39,119))
            p.setBrush(QBrush(g)); p.drawRoundedRect(pad,cy-th//2,fw,th,2,2)
        hx=pad+fw
        gw=QRadialGradient(hx,cy,12); gw.setColorAt(0,QColor(167,139,250,90)); gw.setColorAt(1,QColor(0,0,0,0))
        p.setBrush(QBrush(gw)); p.drawEllipse(hx-12,cy-12,24,24)
        p.setBrush(QBrush(Qt.white)); p.setPen(QPen(QColor(147,51,234,200),1.5))
        p.drawEllipse(hx-5,cy-5,10,10); p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  TRACK ROW
# ══════════════════════════════════════════════════════════════════════════════
class TrackRow(QWidget):
    artist_clicked = pyqtSignal(str)
    def __init__(self,data:dict,idx:int,parent=None):
        super().__init__(parent); self.data=data; self.idx=idx; self._hi=False
        make_transparent(self); self._build()
    def _build(self):
        lay=QHBoxLayout(self); lay.setContentsMargins(10,7,16,7); lay.setSpacing(12)
        n=QLabel(str(self.idx+1)); n.setFixedWidth(28); n.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        n.setStyleSheet("color:rgba(255,255,255,55);font-size:11px;"); lay.addWidget(n)
        self._thumb=MiniThumb()
        url=_thumb_url(self.data)
        if url: self._thumb.set_url(url)
        lay.addWidget(self._thumb)
        info=QVBoxLayout(); info.setSpacing(2); info.setContentsMargins(0,0,0,0)
        title=self.data.get("title","Unknown"); artist=self.data.get("uploader") or self.data.get("channel","")
        tl=QLabel((title[:62]+"…") if len(title)>62 else title)
        tl.setStyleSheet("color:rgba(255,255,255,215);font-size:13px;font-weight:500;background:transparent;")
        al=ClickableLabel(artist[:50])
        al.setStyleSheet("color:rgba(167,139,250,190);font-size:11px;background:transparent;")
        al.clicked.connect(self.artist_clicked)
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
            g.setColorAt(0,QColor(124,58,237,45)); g.setColorAt(.6,QColor(219,39,119,20)); g.setColorAt(1,QColor(0,0,0,0))
            p.setBrush(QBrush(g)); p.setPen(QPen(QColor(147,51,234,50),1))
            p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),10,10); p.end()
        super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  SKELETON ROW
# ══════════════════════════════════════════════════════════════════════════════
class SkeletonRow(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); make_transparent(self)
        self._phase=random.uniform(0,1)
        t=QTimer(self); t.timeout.connect(self._tick); t.start(35)
    def _tick(self): self._phase=(self._phase+0.022)%1.0; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w=self.width(); h=self.height()
        p.setBrush(QBrush(QColor(255,255,255,7))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(8,3,w-16,h-6,10,10)
        p.setBrush(QBrush(QColor(255,255,255,12)))
        p.drawRoundedRect(44,10,46,34,6,6)
        p.drawRoundedRect(104,13,int(w*.38),10,4,4)
        p.drawRoundedRect(104,30,int(w*.22),8,4,4)
        p.drawRoundedRect(w-68,21,44,8,4,4)
        sw=int((w+240)*self._phase)-60
        sg=QLinearGradient(sw,0,sw+180,0)
        sg.setColorAt(0,QColor(200,140,255,0)); sg.setColorAt(.45,QColor(200,140,255,20))
        sg.setColorAt(.55,QColor(255,200,255,28)); sg.setColorAt(1,QColor(200,140,255,0))
        p.setBrush(QBrush(sg)); p.drawRoundedRect(8,3,w-16,h-6,10,10); p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  EP CARD  (artist profile horizontal grid)
# ══════════════════════════════════════════════════════════════════════════════
class EpCard(QWidget):
    play_requested = pyqtSignal(dict)
    _W=185; _ART=180
    def __init__(self,data:dict,idx:int=0,parent=None):
        super().__init__(parent); self.data=data; self._hov=False
        make_transparent(self); self.setFixedWidth(self._W); self.setCursor(Qt.PointingHandCursor)
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,10); lay.setSpacing(6)
        self._thumb=ThumbLabel(self._ART,10,self); self._thumb.setFixedSize(self._ART,self._ART)
        url=_thumb_url(data)
        if url: self._thumb.set_url(url)
        lay.addWidget(self._thumb,0,Qt.AlignHCenter)
        title=data.get("title","Unknown")
        tl=QLabel((title[:22]+"…") if len(title)>22 else title)
        tl.setStyleSheet("color:rgba(255,255,255,215);font-size:12px;font-weight:600;background:transparent;")
        lay.addWidget(tl)
        dur=int(data.get("duration") or 0)
        meta=QLabel(f"Single  •  {dur//60}:{dur%60:02d}" if dur else "Single")
        meta.setStyleSheet("color:rgba(255,255,255,75);font-size:11px;background:transparent;")
        lay.addWidget(meta)
    def enterEvent(self,e): self._hov=True; self.update()
    def leaveEvent(self,e): self._hov=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self.play_requested.emit(self.data)
    def paintEvent(self,e):
        if self._hov:
            p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(QColor(255,255,255,8))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),12,12); p.end()
        super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  PLAYLIST PICKER MODAL  (glass dark dialog)
# ══════════════════════════════════════════════════════════════════════════════
class PlaylistPickerModal(QDialog):
    """
    Dark glass modal for 'Add to playlist' and 'New playlist'.
    Returns the selected playlist id via .exec_() + .result_pid.
    """
    def __init__(self, playlists: dict, parent=None):
        super().__init__(parent)
        self.result_pid: Optional[str] = None
        self.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(360)
        self._build(playlists)

    def _build(self, playlists: dict):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        card=QWidget()
        card.setStyleSheet("""QWidget{background:rgba(12,5,30,245);
            border:1px solid rgba(255,255,255,18);border-radius:18px;}""")
        cl=QVBoxLayout(card); cl.setContentsMargins(24,22,24,22); cl.setSpacing(10)

        hdr=QHBoxLayout()
        ttl=QLabel("Add to Playlist")
        ttl.setStyleSheet("color:white;font-size:16px;font-weight:700;background:transparent;")
        close=QPushButton("✕"); close.setFixedSize(28,28)
        close.setStyleSheet("""QPushButton{background:rgba(255,255,255,12);border-radius:14px;
            color:rgba(255,255,255,160);font-size:12px;border:none;}
            QPushButton:hover{background:rgba(255,255,255,22);}""")
        close.clicked.connect(self.reject)
        hdr.addWidget(ttl); hdr.addStretch(); hdr.addWidget(close)
        cl.addLayout(hdr)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(255,255,255,12);")
        cl.addWidget(sep)

        if playlists:
            for pid,info in playlists.items():
                btn=QPushButton(f"  📋  {info.get('name','Untitled')}")
                btn.setStyleSheet("""QPushButton{background:rgba(255,255,255,7);
                    border:1px solid rgba(255,255,255,12);border-radius:10px;
                    color:rgba(255,255,255,200);font-size:13px;padding:10px 16px;text-align:left;}
                    QPushButton:hover{background:rgba(124,58,237,40);border-color:rgba(147,51,234,80);color:white;}""")
                btn.clicked.connect(lambda _,p=pid: self._pick(p))
                cl.addWidget(btn)
            cl.addWidget(QFrame())  # spacer
        else:
            no=QLabel("No playlists yet.")
            no.setStyleSheet("color:rgba(255,255,255,60);font-size:13px;background:transparent;")
            no.setAlignment(Qt.AlignCenter); cl.addWidget(no)

        root.addWidget(card)

    def _pick(self,pid:str):
        self.result_pid=pid; self.accept()

    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(0,0,0,0)); p.end(); super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  NEW PLAYLIST MODAL
# ══════════════════════════════════════════════════════════════════════════════
class NewPlaylistModal(QDialog):
    """Dark glass modal for naming a new playlist."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_name: Optional[str] = None
        self.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(340)
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        card=QWidget()
        card.setStyleSheet("QWidget{background:rgba(12,5,30,245);border:1px solid rgba(255,255,255,18);border-radius:18px;}")
        cl=QVBoxLayout(card); cl.setContentsMargins(24,22,24,22); cl.setSpacing(14)

        hdr=QHBoxLayout()
        ttl=QLabel("New Playlist")
        ttl.setStyleSheet("color:white;font-size:16px;font-weight:700;background:transparent;")
        close=QPushButton("✕"); close.setFixedSize(28,28)
        close.setStyleSheet("QPushButton{background:rgba(255,255,255,12);border-radius:14px;color:rgba(255,255,255,160);font-size:12px;border:none;} QPushButton:hover{background:rgba(255,255,255,22);}")
        close.clicked.connect(self.reject)
        hdr.addWidget(ttl); hdr.addStretch(); hdr.addWidget(close)
        cl.addLayout(hdr)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(255,255,255,12);"); cl.addWidget(sep)

        self._input=QLineEdit()
        self._input.setPlaceholderText("Playlist name…")
        self._input.setStyleSheet("""
            QLineEdit{background:rgba(255,255,255,10);border:1px solid rgba(255,255,255,22);
                border-radius:10px;padding:10px 16px;color:white;font-size:14px;}
            QLineEdit:focus{border-color:rgba(147,51,234,160);background:rgba(147,51,234,10);}
        """)
        self._input.returnPressed.connect(self._confirm)
        cl.addWidget(self._input)

        confirm=QPushButton("Create")
        confirm.setStyleSheet("""
            QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(124,58,237,200),stop:1 rgba(219,39,119,200));
                border:none;border-radius:10px;color:white;font-size:14px;font-weight:600;padding:10px;}
            QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(147,51,234,230),stop:1 rgba(236,72,153,230));}
        """)
        confirm.clicked.connect(self._confirm)
        cl.addWidget(confirm)
        root.addWidget(card)

    def _confirm(self):
        name=self._input.text().strip()
        if name: self.result_name=name; self.accept()

    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(0,0,0,0)); p.end(); super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  EXPANDED PLAYER OVERLAY
# ══════════════════════════════════════════════════════════════════════════════
class ExpandedPlayerOverlay(QWidget):
    close_requested   = pyqtSignal()
    seek_sig          = pyqtSignal(int)
    like_sig          = pyqtSignal()
    loop_sig          = pyqtSignal(bool)
    prev_sig          = pyqtSignal()
    play_pause_sig    = pyqtSignal()
    next_sig          = pyqtSignal()
    stop_sig          = pyqtSignal()
    artist_search_sig = pyqtSignal(str)
    volume_sig        = pyqtSignal(int)

    _TABS = ["Up Next", "Related"]

    def __init__(self,parent=None):
        super().__init__(parent); make_transparent(self)
        self._dur_ms=0; self._seeking=False; self._liked=False; self._looping=False
        self._cur_tab=0
        self._cached_related: list = []   # persists even when overlay is closed
        self._stored_queue:   list = []   # engine queue dicts, always kept fresh
        self._stored_idx:     int  = -1   # current index in engine queue
        self._build(); self.hide()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Top bar
        top_w=QWidget(); make_transparent(top_w)
        top=QHBoxLayout(top_w); top.setContentsMargins(32,14,32,4)
        close=CircleBtn("∨",38,parent=self); close.clicked.connect(self.close_requested)
        top.addStretch(); top.addWidget(close); root.addWidget(top_w)

        body=QWidget(); make_transparent(body)
        split=QHBoxLayout(body); split.setContentsMargins(48,0,48,20); split.setSpacing(56)

        # ── LEFT ─────────────────────────────────────────────────────────────
        lw=QWidget(); make_transparent(lw); lw.setFixedWidth(380)
        ll=QVBoxLayout(lw); ll.setSpacing(0); ll.setAlignment(Qt.AlignTop|Qt.AlignHCenter)

        self._big_thumb=ThumbLabel(320,20,self); self._big_thumb.setFixedSize(320,320)
        ll.addWidget(self._big_thumb,0,Qt.AlignHCenter); ll.addSpacing(20)

        self._title_lbl=QLabel("Nothing playing")
        self._title_lbl.setStyleSheet("color:white;font-size:22px;font-weight:700;background:transparent;")
        self._title_lbl.setAlignment(Qt.AlignCenter); self._title_lbl.setWordWrap(True)
        ll.addWidget(self._title_lbl); ll.addSpacing(4)

        ar_w=QWidget(); make_transparent(ar_w)
        ar=QHBoxLayout(ar_w); ar.setContentsMargins(0,0,0,0); ar.setAlignment(Qt.AlignCenter); ar.setSpacing(10)
        self._artist_lbl=ClickableLabel("—")
        self._artist_lbl.setStyleSheet("color:rgba(167,139,250,210);font-size:14px;background:transparent;")
        self._artist_lbl.setAlignment(Qt.AlignCenter)
        self._artist_lbl.clicked.connect(lambda t: self.artist_search_sig.emit(t) if t and t!="—" else None)
        self._like_btn=CircleBtn("♡",34,parent=self); self._like_btn.clicked.connect(self.like_sig)
        ar.addWidget(self._artist_lbl); ar.addWidget(self._like_btn)
        ll.addWidget(ar_w); ll.addSpacing(18)

        cw=QWidget(); make_transparent(cw)
        ctrl=QHBoxLayout(cw); ctrl.setSpacing(10); ctrl.setAlignment(Qt.AlignCenter)
        self._loop_btn=CircleBtn("⟳",42,parent=self); self._loop_btn.clicked.connect(self._on_loop)
        self._prev_btn=CircleBtn("⏮",52,parent=self); self._prev_btn.clicked.connect(self.prev_sig)
        self._play_btn=CircleBtn("▶",68,accent=True,parent=self); self._play_btn.clicked.connect(self.play_pause_sig)
        self._next_btn=CircleBtn("⏭",52,parent=self); self._next_btn.clicked.connect(self.next_sig)
        self._stop_btn=CircleBtn("⏹",42,parent=self); self._stop_btn.clicked.connect(self.stop_sig)
        for w in (self._loop_btn,self._prev_btn,self._play_btn,self._next_btn,self._stop_btn): ctrl.addWidget(w)
        ll.addWidget(cw); ll.addSpacing(12)

        sk_w=QWidget(); make_transparent(sk_w)
        sk=QHBoxLayout(sk_w); sk.setSpacing(10); sk.setContentsMargins(0,0,0,0)
        self._pos_lbl=QLabel("0:00"); self._pos_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;")
        self._pos_lbl.setFixedWidth(40); self._pos_lbl.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self._seek=SeekBar(self); self._seek.pressed.connect(lambda:setattr(self,"_seeking",True)); self._seek.released.connect(self._on_seek)
        self._dur_lbl=QLabel("0:00"); self._dur_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;"); self._dur_lbl.setFixedWidth(40)
        sk.addWidget(self._pos_lbl); sk.addWidget(self._seek,1); sk.addWidget(self._dur_lbl)
        ll.addWidget(sk_w); ll.addSpacing(10)

        vw=QWidget(); make_transparent(vw)
        vr=QHBoxLayout(vw); vr.setAlignment(Qt.AlignCenter); vr.setSpacing(10)
        vl=QLabel("🔊"); vl.setStyleSheet("font-size:14px;color:rgba(255,255,255,110);background:transparent;")
        self._vol=QSlider(Qt.Horizontal,self); self._vol.setRange(0,100); self._vol.setValue(70)
        self._vol.setFixedWidth(150); self._vol.setCursor(Qt.PointingHandCursor); make_transparent(self._vol)
        self._vol.setStyleSheet("""
            QSlider::groove:horizontal{background:rgba(255,255,255,20);height:4px;border-radius:2px;}
            QSlider::sub-page:horizontal{background:rgba(167,139,250,190);border-radius:2px;}
            QSlider::handle:horizontal{background:white;border:2px solid rgba(124,58,237,200);width:12px;height:12px;margin:-4px 0;border-radius:6px;}
        """)
        self._vol.valueChanged.connect(self.volume_sig)
        vr.addWidget(vl); vr.addWidget(self._vol); ll.addWidget(vw)
        split.addWidget(lw)

        # ── RIGHT ─────────────────────────────────────────────────────────────
        rw=QWidget(); make_transparent(rw)
        rl=QVBoxLayout(rw); rl.setSpacing(0); rl.setContentsMargins(0,0,0,0)

        # Underline-style tab bar — plain QPushButton, no make_transparent so hit-testing is reliable
        tbw=QWidget(); tbw.setFixedHeight(44); make_transparent(tbw)
        tb=QHBoxLayout(tbw); tb.setContentsMargins(0,0,0,0); tb.setSpacing(0)
        self._tab_btns: list = []
        for i,name in enumerate(self._TABS):
            btn=QPushButton(name); btn.setParent(tbw); btn.setCheckable(True); btn.setFlat(True)
            btn.setFixedHeight(44)
            btn.setStyleSheet("""
                QPushButton{background:rgba(0,0,0,0);border:none;
                    border-bottom:2px solid transparent;
                    padding:0 28px;color:rgba(255,255,255,90);font-size:13px;font-weight:500;}
                QPushButton:checked{color:white;font-weight:700;
                    border-bottom:2px solid rgba(255,255,255,220);}
                QPushButton:hover:!checked{color:rgba(255,255,255,200);
                    background:rgba(255,255,255,6);}
            """)
            btn.clicked.connect(lambda _,idx=i:self._switch_tab(idx))
            tb.addWidget(btn); self._tab_btns.append(btn)
        tb.addStretch(); rl.addWidget(tbw)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(255,255,255,12);"); rl.addWidget(sep)

        # QStackedWidget — guaranteed single-visible-child, no manual show/hide bugs
        self._stack=QStackedWidget(); make_transparent(self._stack)
        self._stack.setStyleSheet("background:transparent;")

        # Page 0 – Up Next
        p0=QWidget(); make_transparent(p0)
        p0l=QVBoxLayout(p0); p0l.setContentsMargins(0,8,0,0); p0l.setSpacing(4)
        self._ctx_lbl=QLabel("Playing from queue")
        self._ctx_lbl.setStyleSheet("color:rgba(255,255,255,55);font-size:11px;padding:0 4px;background:transparent;")
        p0l.addWidget(self._ctx_lbl)
        self._queue_list=GlassListWidget(p0); p0l.addWidget(self._queue_list,1)
        self._stack.addWidget(p0)

        # Page 1 – Related
        p1=QWidget(); make_transparent(p1)
        p1l=QVBoxLayout(p1); p1l.setContentsMargins(0,8,0,0); p1l.setSpacing(0)
        self._related_list=GlassListWidget(p1); p1l.addWidget(self._related_list,1)
        self._stack.addWidget(p1)

        rl.addWidget(self._stack,1); split.addWidget(rw,1); root.addWidget(body,1)
        self._tab_btns[0].setChecked(True)

    # ── Public API ─────────────────────────────────────────────────────────
    def set_track_info(self,title:str,artist:str):
        t=(title[:40]+"…") if len(title)>40 else title
        self._title_lbl.setText(t); self._artist_lbl.setText(artist or "—")
    def set_thumbnail(self,url:str): self._big_thumb.set_url(url)
    def set_playing(self,playing:bool): self._play_btn._icon="⏸" if playing else "▶"; self._play_btn.update()
    def set_position(self,ms:int):
        if self._seeking: return
        s=ms//1000; m,s=divmod(s,60); self._pos_lbl.setText(f"{m}:{s:02d}")
        if self._dur_ms>0: self._seek.setValue(ms/self._dur_ms)
    def set_duration(self,ms:int):
        self._dur_ms=ms; s=ms//1000; m,s=divmod(s,60); self._dur_lbl.setText(f"{m}:{s:02d}")
    def set_liked(self,liked:bool):
        self._liked=liked; self._like_btn._icon="♥" if liked else "♡"
        self._like_btn._active=liked; self._like_btn.update()
    def set_volume(self,vol:int):
        self._vol.blockSignals(True); self._vol.setValue(vol); self._vol.blockSignals(False)

    def store_queue(self, queue: list, current_idx: int):
        """
        Always called (even when closed) to keep the overlay's queue fresh.
        `queue` is a list of dicts from the engine.
        """
        self._stored_queue = list(queue)
        self._stored_idx   = current_idx

    def update_queue(self, queue: list, current_idx: int):
        """Store AND immediately render the Up Next list."""
        self.store_queue(queue, current_idx)
        self._render_queue()

    def _render_queue(self):
        self._queue_list.clear()
        coming = [_as_dict(t) for i,t in enumerate(self._stored_queue) if i > self._stored_idx]
        if not coming:
            # Show skeletons while queue is building
            for _ in range(5):
                item=QListWidgetItem(self._queue_list)
                item.setSizeHint(QSize(0,58))
                self._queue_list.addItem(item)
                self._queue_list.setItemWidget(item, SkeletonRow())
        else:
            for i,t in enumerate(coming):
                item=QListWidgetItem(self._queue_list)
                row=TrackRow(t, self._stored_idx+1+i); item.setSizeHint(QSize(0,58))
                self._queue_list.addItem(item); self._queue_list.setItemWidget(item,row)

    def set_related(self, tracks: list):
        """Store and render the Related list; shows skeletons while empty."""
        self._cached_related = list(tracks)
        self._related_list.clear()
        if tracks:
            for i,t in enumerate(tracks):
                item=QListWidgetItem(self._related_list)
                row=TrackRow(_as_dict(t),i); item.setSizeHint(QSize(0,58))
                self._related_list.addItem(item); self._related_list.setItemWidget(item,row)
        else:
            for _ in range(5):
                item=QListWidgetItem(self._related_list)
                item.setSizeHint(QSize(0,58))
                self._related_list.addItem(item)
                self._related_list.setItemWidget(item, SkeletonRow())

    def show_on_open(self):
        """Called when overlay opens — render from stored data."""
        self._render_queue()
        self.set_related(self._cached_related)
        # Switch back to Up Next tab each time it opens
        self._switch_tab(0)

    # ── Internal ───────────────────────────────────────────────────────────
    def _switch_tab(self,idx:int):
        self._cur_tab=idx
        self._stack.setCurrentIndex(idx)
        for i,btn in enumerate(self._tab_btns):
            btn.setChecked(i==idx)

    def _on_loop(self):
        self._looping=not self._looping; self._loop_btn.setActive(self._looping); self.loop_sig.emit(self._looping)
    def _on_seek(self,ratio:float):
        self._seeking=False
        if self._dur_ms>0: self.seek_sig.emit(int(ratio*self._dur_ms))

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        bg=QLinearGradient(0,0,w,h); bg.setColorAt(0,QColor(6,2,18,235)); bg.setColorAt(1,QColor(3,1,10,248))
        p.fillRect(0,0,w,h,bg)
        g1=QRadialGradient(w*.22,h*.35,h*.6); g1.setColorAt(0,QColor(100,30,200,30)); g1.setColorAt(1,QColor(0,0,0,0)); p.fillRect(0,0,w,h,g1)
        g2=QRadialGradient(w*.78,h*.7,h*.5); g2.setColorAt(0,QColor(180,30,110,22)); g2.setColorAt(1,QColor(0,0,0,0)); p.fillRect(0,0,w,h,g2)
        p.end(); super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  ARTIST PROFILE VIEW
# ══════════════════════════════════════════════════════════════════════════════
class ArtistProfileView(QWidget):
    back_requested       = pyqtSignal()
    track_play_requested = pyqtSignal(dict,int)

    def __init__(self,parent=None):
        super().__init__(parent); make_transparent(self)
        self._artist=""; self._tracks:list=[]; self._build(); self.hide()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        hero=QWidget(); make_transparent(hero); hero.setFixedHeight(160)
        hl=QVBoxLayout(hero); hl.setContentsMargins(32,24,32,16); hl.setSpacing(6)
        br=QHBoxLayout()
        self._back_btn=CircleBtn("←",38,parent=self); self._back_btn.clicked.connect(self.back_requested)
        br.addWidget(self._back_btn); br.addStretch(); hl.addLayout(br)
        self._name_lbl=QLabel("Artist")
        self._name_lbl.setStyleSheet("color:white;font-size:32px;font-weight:800;background:transparent;letter-spacing:-1px;")
        hl.addWidget(self._name_lbl)
        self._meta_lbl=QLabel("")
        self._meta_lbl.setStyleSheet("color:rgba(167,139,250,180);font-size:12px;background:transparent;")
        hl.addWidget(self._meta_lbl); root.addWidget(hero)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(255,255,255,12);"); root.addWidget(sep)

        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollBar:vertical{background:transparent;width:4px;} QScrollBar::handle:vertical{background:rgba(255,255,255,22);border-radius:2px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        make_transparent(scroll)
        bw=QWidget(); make_transparent(bw)
        bl=QVBoxLayout(bw); bl.setContentsMargins(28,16,28,24); bl.setSpacing(0)

        def slbl(t):
            lb=QLabel(t); lb.setStyleSheet("color:white;font-size:18px;font-weight:700;background:transparent;margin-bottom:4px;"); return lb

        bl.addWidget(slbl("Popular")); bl.addSpacing(6)
        self._pop_list=GlassListWidget()
        self._pop_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pop_list.setFixedHeight(6*62+4); self._pop_list.itemDoubleClicked.connect(self._on_pop_dbl)
        bl.addWidget(self._pop_list); bl.addSpacing(28); bl.addWidget(slbl("Singles & EPs")); bl.addSpacing(10)

        ep_s=QScrollArea(); ep_s.setFixedHeight(255)
        ep_s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); ep_s.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ep_s.setWidgetResizable(True); ep_s.setStyleSheet("QScrollArea{background:transparent;border:none;}"); make_transparent(ep_s)
        self._ep_container=QWidget(); make_transparent(self._ep_container)
        self._ep_layout=QHBoxLayout(self._ep_container); self._ep_layout.setContentsMargins(0,0,0,0); self._ep_layout.setSpacing(14); self._ep_layout.addStretch()
        ep_s.setWidget(self._ep_container)
        ep_s.wheelEvent=lambda e:(ep_s.horizontalScrollBar().setValue(ep_s.horizontalScrollBar().value()-e.angleDelta().y()) or e.accept())
        bl.addWidget(ep_s); bl.addStretch()
        scroll.setWidget(bw); root.addWidget(scroll,1)

    def populate(self,artist:str,tracks:list):
        self._artist=artist; self._tracks=tracks
        self._name_lbl.setText(artist); self._meta_lbl.setText(f"{len(tracks)} tracks found")
        self._pop_list.clear()
        for i,t in enumerate(tracks[:6]):
            item=QListWidgetItem(self._pop_list)
            row=TrackRow(_as_dict(t),i); item.setSizeHint(QSize(0,60))
            self._pop_list.addItem(item); self._pop_list.setItemWidget(item,row)
        while self._ep_layout.count()>1:
            it=self._ep_layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for i,t in enumerate(tracks):
            card=EpCard(_as_dict(t),i,self._ep_container); card.play_requested.connect(self._on_ep_play)
            self._ep_layout.insertWidget(self._ep_layout.count()-1,card)

    def _on_pop_dbl(self,item):
        r=self._pop_list.row(item)
        if 0<=r<len(self._tracks): self.track_play_requested.emit(_as_dict(self._tracks[r]),r)

    def _on_ep_play(self,data:dict):
        try: idx=next(i for i,t in enumerate(self._tracks) if _as_dict(t).get("id")==data.get("id"))
        except StopIteration: idx=0
        self.track_play_requested.emit(data,idx)

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        bg=QLinearGradient(0,0,0,h); bg.setColorAt(0,QColor(8,3,22,240)); bg.setColorAt(1,QColor(4,1,12,245))
        p.fillRect(0,0,w,h,bg)
        gw=QRadialGradient(w*.5,0,h*.6); gw.setColorAt(0,QColor(100,30,200,35)); gw.setColorAt(1,QColor(0,0,0,0)); p.fillRect(0,0,w,h,gw)
        p.end(); super().paintEvent(e)


# ══════════════════════════════════════════════════════════════════════════════
#  GLASS CANVAS  (main widget)
# ══════════════════════════════════════════════════════════════════════════════
class GlassCanvas(QWidget):
    SIDEBAR_W   = 230
    PLAYERBAR_H = 100
    SEARCH_H    = 72
    HEADER_H    = 80

    search_submitted     = pyqtSignal(str)
    track_double_clicked = pyqtSignal(dict,int)
    add_to_playlist      = pyqtSignal(dict)
    like_track_sig       = pyqtSignal(dict)
    nav_changed          = pyqtSignal(str)
    new_playlist_sig     = pyqtSignal()
    new_playlist_name_sig= pyqtSignal(str)   # carries the name directly
    play_pause_sig       = pyqtSignal()
    prev_sig             = pyqtSignal()
    next_sig             = pyqtSignal()
    stop_sig             = pyqtSignal()
    seek_sig             = pyqtSignal(int)
    volume_sig           = pyqtSignal(int)
    like_current_sig     = pyqtSignal()
    loop_sig             = pyqtSignal(bool)
    artist_search_sig    = pyqtSignal(str)
    scroll_near_bottom   = pyqtSignal()
    add_to_playlist_current = pyqtSignal()   # from the playbar ➕ button

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;"); make_transparent(self)
        _DrainTimer.ensure()
        self._orbs:list=[]; self._sparks:list=[]
        self._W=self._H=0; self._tracks:list=[]; self._cur_track=-1
        self._nav_active="home"; self._pl_btns:dict={}
        self._dur_ms=0; self._seeking=False; self._liked=False; self._looping=False
        self._section_title="Discover"; self._section_sub="Popular tracks right now"
        self._expanded=False; self._artist_view_active=False
        self._build_widgets()
        self._anim=QTimer(self); self._anim.timeout.connect(self._tick); self._anim.start(33)

    # ── Build ─────────────────────────────────────────────────────────────
    def _build_widgets(self):
        self._search_input=GlassLineEdit(self)
        self._search_input.setPlaceholderText("Search songs, artists, albums…")
        self._search_input.returnPressed.connect(self._on_search)
        self._search_btn=GlassButton("Search",self); self._search_btn.setFixedWidth(100)
        self._search_btn.clicked.connect(self._on_search)

        nav_defs=[("search","🔍  Search"),("home","🏠  Home"),
                  ("liked","♥  Liked Songs"),("history","🕐  History")]
        self._nav_btns:dict={}
        for sid,label in nav_defs:
            btn=GlassNavButton(label,self); btn.clicked.connect(lambda _,s=sid:self._on_nav(s))
            self._nav_btns[sid]=btn

        self._new_pl_btn=QPushButton("  ＋  New Playlist",self)
        self._new_pl_btn.setFlat(True); make_transparent(self._new_pl_btn)
        self._new_pl_btn.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:10px;
                padding:8px 16px;text-align:left;color:rgba(167,139,250,200);font-size:12px;}
            QPushButton:hover{background:rgba(124,58,237,20);color:#c4b5fd;}
        """)
        self._new_pl_btn.clicked.connect(self._on_new_playlist_btn); self._new_pl_btn.setMinimumHeight(36)

        self._list=GlassListWidget(self)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_dbl)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_ctx)
        self._list.near_bottom.connect(self.scroll_near_bottom)

        self._status_lbl=QLabel(self); self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color:rgba(255,255,255,80);font-size:14px;background:transparent;")
        self._status_lbl.hide()

        # Player bar widgets
        self._thumb=ThumbLabel(62,10,self)
        self._title_lbl=QLabel("Nothing playing",self)
        self._title_lbl.setStyleSheet("color:white;font-size:14px;font-weight:600;background:transparent;")
        self._artist_lbl=QLabel("—",self)
        self._artist_lbl.setStyleSheet("color:rgba(255,255,255,120);font-size:11px;background:transparent;")

        self._like_btn  =CircleBtn("♡",36,parent=self); self._like_btn.clicked.connect(self.like_current_sig)
        self._addpl_btn =CircleBtn("➕",34,parent=self); self._addpl_btn.clicked.connect(self.add_to_playlist_current)
        self._loop_btn  =CircleBtn("⟳",40,parent=self); self._loop_btn.clicked.connect(self._on_loop)
        self._prev_btn  =CircleBtn("⏮",48,parent=self); self._prev_btn.clicked.connect(self.prev_sig)
        self._play_btn  =CircleBtn("▶",64,accent=True,parent=self); self._play_btn.clicked.connect(self.play_pause_sig)
        self._next_btn  =CircleBtn("⏭",48,parent=self); self._next_btn.clicked.connect(self.next_sig)
        self._stop_btn  =CircleBtn("⏹",40,parent=self); self._stop_btn.clicked.connect(self.stop_sig)

        self._pos_lbl=QLabel("0:00",self); self._pos_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;")
        self._dur_lbl=QLabel("0:00",self); self._dur_lbl.setStyleSheet("color:rgba(255,255,255,90);font-size:11px;background:transparent;")
        self._seek_bar=SeekBar(self)
        self._seek_bar.pressed.connect(lambda:setattr(self,"_seeking",True))
        self._seek_bar.released.connect(self._on_seek)

        self._vol_lbl=QLabel("🔊",self); self._vol_lbl.setStyleSheet("font-size:14px;color:rgba(255,255,255,130);background:transparent;")
        self._vol_slider=QSlider(Qt.Horizontal,self)
        self._vol_slider.setRange(0,100); self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(88); self._vol_slider.setCursor(Qt.PointingHandCursor)
        make_transparent(self._vol_slider)
        self._vol_slider.setStyleSheet("""
            QSlider::groove:horizontal{background:rgba(255,255,255,20);height:3px;border-radius:2px;}
            QSlider::sub-page:horizontal{background:rgba(167,139,250,190);border-radius:2px;}
            QSlider::handle:horizontal{background:white;border:2px solid rgba(124,58,237,200);
                width:10px;height:10px;margin:-3px 0;border-radius:5px;}
        """)
        self._vol_slider.valueChanged.connect(self._on_vol)
        self._nav_btns["home"].setChecked(True)

        # Playlist scroll
        self._pl_scroll=QScrollArea(self); self._pl_scroll.setWidgetResizable(True)
        self._pl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pl_scroll.setStyleSheet("background:transparent;border:none;"); make_transparent(self._pl_scroll)
        self._pl_container=QWidget(); make_transparent(self._pl_container); self._pl_container.setStyleSheet("background:transparent;")
        self._pl_vlay=QVBoxLayout(self._pl_container); self._pl_vlay.setContentsMargins(0,0,0,0); self._pl_vlay.setSpacing(2); self._pl_vlay.addStretch()
        self._pl_scroll.setWidget(self._pl_container)

        # Overlays
        self._exp=ExpandedPlayerOverlay(self)
        self._exp.close_requested.connect(self._toggle_expanded)
        self._exp.seek_sig.connect(self.seek_sig)
        self._exp.like_sig.connect(self.like_current_sig)
        self._exp.loop_sig.connect(self._on_exp_loop)
        self._exp.prev_sig.connect(self.prev_sig)
        self._exp.play_pause_sig.connect(self.play_pause_sig)
        self._exp.next_sig.connect(self.next_sig)
        self._exp.stop_sig.connect(self.stop_sig)
        self._exp.artist_search_sig.connect(self.artist_search_sig)
        self._exp.volume_sig.connect(self._on_exp_vol)

        self._artist_view=ArtistProfileView(self)
        self._artist_view.back_requested.connect(self._on_artist_back)
        self._artist_view.track_play_requested.connect(self._on_artist_play)

    # ── Layout ─────────────────────────────────────────────────────────────
    def resizeEvent(self,e):
        super().resizeEvent(e)
        w=self.width(); h=self.height()
        sw=self.SIDEBAR_W; ph=self.PLAYERBAR_H; sh=self.SEARCH_H; hh=self.HEADER_H
        cx=sw; cw=w-sw
        self._W=w; self._H=h
        self._orbs=[Orb(w,h,i) for i in range(9)]
        self._sparks=[Spark(w,h) for _ in range(70)]

        by=60
        for btn in self._nav_btns.values(): btn.setGeometry(10,by,sw-20,42); by+=46
        by+=8; by+=22
        self._new_pl_btn.setGeometry(10,by,sw-20,36); by+=40
        self._pl_scroll.setGeometry(10,by,sw-20,h-ph-by-16)

        self._search_input.setGeometry(cx+20,12,cw-160,48)
        self._search_btn.setGeometry(cx+cw-120,12,100,48)

        list_top=sh+hh
        self._list.setGeometry(cx,list_top,cw,h-ph-list_top)
        self._status_lbl.setGeometry(cx,list_top,cw,h-ph-list_top)

        py=h-ph
        # Left info zone
        self._thumb.setGeometry(20,py+19,62,62)
        self._title_lbl.setGeometry(92,py+24,170,22)
        self._artist_lbl.setGeometry(92,py+50,170,18)
        self._like_btn.setGeometry(270,py+32,36,36)
        self._addpl_btn.setGeometry(310,py+33,34,34)

        # Centre transport
        mid=w//2; gap=10
        total=40+gap+48+gap+64+gap+48+gap+40
        bx=mid-total//2
        self._loop_btn.setGeometry(bx,py+18,40,40); bx+=40+gap
        self._prev_btn.setGeometry(bx,py+14,48,48); bx+=48+gap
        self._play_btn.setGeometry(bx,py+10,64,64); bx+=64+gap
        self._next_btn.setGeometry(bx,py+14,48,48); bx+=48+gap
        self._stop_btn.setGeometry(bx,py+18,40,40)

        # Seek
        self._pos_lbl.setGeometry(mid-380,py+68,40,20)
        self._seek_bar.setGeometry(mid-336,py+66,672,22)
        self._dur_lbl.setGeometry(mid+340,py+68,40,20)

        # Volume
        self._vol_lbl.setGeometry(w-140,py+36,24,24)
        self._vol_slider.setGeometry(w-112,py+38,88,20)

        self._exp.setGeometry(0,0,w,h)
        self._artist_view.setGeometry(cx,0,cw,h-ph)
        if self._expanded: self._exp.show(); self._exp.raise_()
        if self._artist_view_active: self._artist_view.show(); self._artist_view.raise_()

    # ── Animation / Paint ─────────────────────────────────────────────────
    def _tick(self):
        for o in self._orbs: o.update()
        for s in self._sparks: s.update()
        self.update()

    def mousePressEvent(self,e):
        """Click anywhere in the player bar to toggle expanded view."""
        py=self.height()-self.PLAYERBAR_H
        if e.y()>=py and not self._expanded:
            # Only expand on click, dedicated buttons handle collapse
            x=e.x()
            # Avoid stealing clicks from the actual control buttons
            if x<self.SIDEBAR_W: return
            # Check if click is NOT on a child button (buttons eat their own events)
            self._toggle_expanded()
        super().mousePressEvent(e)

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w=self.width(); h=self.height()
        if w<1 or h<1: p.end(); return
        sw=self.SIDEBAR_W; ph=self.PLAYERBAR_H; sh=self.SEARCH_H; hh=self.HEADER_H

        bg=QLinearGradient(0,0,w,h)
        bg.setColorAt(0,QColor(7,3,18)); bg.setColorAt(.5,QColor(14,5,32)); bg.setColorAt(1,QColor(5,2,14))
        p.fillRect(0,0,w,h,bg)
        warm=QRadialGradient(w*.85,h*.75,h*.7); warm.setColorAt(0,QColor(180,55,10,55)); warm.setColorAt(1,QColor(0,0,0,0)); p.fillRect(0,0,w,h,warm)

        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for o in self._orbs: p.setBrush(QBrush(o.grad())); p.setPen(Qt.NoPen); p.drawPath(o.path())
        for s in self._sparks:
            al=int(s.al*s.life); r,g,b=s.c
            p.setBrush(QBrush(QColor(r,g,b,al))); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(s.x,s.y),s.rad,s.rad)

        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        vig=QRadialGradient(w/2,h/2,max(w,h)*.72)
        vig.setColorAt(.3,QColor(0,0,0,0)); vig.setColorAt(.75,QColor(0,0,0,70)); vig.setColorAt(1,QColor(0,0,0,190))
        p.fillRect(0,0,w,h,vig)

        draw_glass_rect(p,QRectF(0,0,sw,h-ph),0,fill_alpha=28,border_alpha=0,highlight=False)
        re=QLinearGradient(sw-1,0,sw+1,0); re.setColorAt(0,QColor(255,255,255,35)); re.setColorAt(1,QColor(255,255,255,0))
        p.fillRect(sw-1,0,2,h,re)
        p.setPen(QColor(255,255,255,230)); f=QFont("Segoe UI",15,QFont.Bold); p.setFont(f)
        p.drawText(QRectF(20,22,sw-24,36),Qt.AlignVCenter,"▶  YTMusicPlayer")
        nav_end_y=60+4*46+8
        p.setPen(QPen(QColor(255,255,255,18),1)); p.drawLine(14,nav_end_y,sw-14,nav_end_y)
        p.setPen(QColor(255,255,255,60)); f2=QFont("Segoe UI",9,QFont.Bold); f2.setLetterSpacing(QFont.AbsoluteSpacing,2); p.setFont(f2)
        p.drawText(QRectF(20,nav_end_y+8,sw-24,20),Qt.AlignVCenter,"LIBRARY")

        draw_glass_rect(p,QRectF(sw,0,w-sw,sh),0,fill_alpha=22,border_alpha=0,highlight=False)
        draw_glass_line(p,sw,sh,w,sh)

        hg=QLinearGradient(sw,sh,w,sh+hh); hg.setColorAt(0,QColor(80,20,160,18)); hg.setColorAt(1,QColor(0,0,0,0)); p.fillRect(sw,sh,w-sw,hh,hg)
        p.setPen(QColor(255,255,255,230)); f3=QFont("Segoe UI",26,QFont.Bold); p.setFont(f3)
        p.drawText(QRectF(sw+24,sh+12,w-sw-48,40),Qt.AlignVCenter,self._section_title)
        p.setPen(QColor(255,255,255,90)); f4=QFont("Segoe UI",11); p.setFont(f4)
        p.drawText(QRectF(sw+24,sh+52,w-sw-48,24),Qt.AlignVCenter,self._section_sub)
        draw_glass_line(p,sw,sh+hh,w,sh+hh)

        py=h-ph
        bg2=QLinearGradient(0,py,0,h); bg2.setColorAt(0,QColor(10,4,28,140)); bg2.setColorAt(1,QColor(6,2,18,170)); p.fillRect(0,py,w,ph,bg2)
        gl=QLinearGradient(0,py,w,py)
        gl.setColorAt(0,QColor(124,58,237,0)); gl.setColorAt(.4,QColor(167,139,250,60))
        gl.setColorAt(.6,QColor(219,39,119,50)); gl.setColorAt(1,QColor(219,39,119,0))
        p.fillRect(0,py,w,2,gl)
        p.setPen(QPen(QColor(255,255,255,15),1)); p.drawLine(sw,py,sw,h)
        p.end()

    # ── Public API ─────────────────────────────────────────────────────────
    def set_tracks(self,tracks:list):
        self._tracks=tracks; self._list.clear(); self._status_lbl.hide()
        for i,t in enumerate(tracks):
            item=QListWidgetItem(self._list)
            row=TrackRow(t,i); item.setSizeHint(QSize(0,60))
            self._list.addItem(item); self._list.setItemWidget(item,row)
            row.artist_clicked.connect(self.artist_search_sig)
        self._list.reset_cool()

    def append_tracks(self,new_tracks:list):
        # Strip trailing skeleton rows
        while self._list.count()>0:
            last=self._list.item(self._list.count()-1)
            if isinstance(self._list.itemWidget(last),SkeletonRow): self._list.takeItem(self._list.count()-1)
            else: break
        start=len(self._tracks); self._tracks.extend(new_tracks)
        for i,t in enumerate(new_tracks,start=start):
            item=QListWidgetItem(self._list)
            row=TrackRow(t,i); item.setSizeHint(QSize(0,60))
            self._list.addItem(item); self._list.setItemWidget(item,row)
            row.artist_clicked.connect(self.artist_search_sig)
        QTimer.singleShot(2300,self._list.reset_cool)

    def append_skeleton_rows(self,count:int=4):
        for _ in range(count):
            item=QListWidgetItem(self._list)
            row=SkeletonRow(); item.setSizeHint(QSize(0,60))
            self._list.addItem(item); self._list.setItemWidget(item,row)

    def show_loading_skeleton(self,count:int=8):
        self._list.clear(); self._status_lbl.hide()
        for _ in range(count):
            item=QListWidgetItem(self._list)
            row=SkeletonRow(); item.setSizeHint(QSize(0,60))
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
        # Always keep overlay queue fresh (even when closed)
        self._exp.store_queue(self._exp._stored_queue, idx)
        if self._expanded: self._exp._render_queue()

    def set_track_info(self,title:str,artist:str):
        t=(title[:26]+"…") if len(title)>26 else title
        self._title_lbl.setText(t); self._artist_lbl.setText(artist)
        self._exp.set_track_info(title,artist)

    def set_thumbnail(self,url:str):
        self._thumb.set_url(url); self._exp.set_thumbnail(url)

    def set_playing(self,playing:bool):
        self._play_btn._icon="⏸" if playing else "▶"; self._play_btn.update()
        self._exp.set_playing(playing)

    def set_position(self,ms:int):
        if self._seeking: return
        s=ms//1000; m,s=divmod(s,60); self._pos_lbl.setText(f"{m}:{s:02d}")
        if self._dur_ms>0: self._seek_bar.setValue(ms/self._dur_ms)
        self._exp.set_position(ms)

    def set_duration(self,ms:int):
        self._dur_ms=ms; s=ms//1000; m,s=divmod(s,60); self._dur_lbl.setText(f"{m}:{s:02d}")
        self._exp.set_duration(ms)

    def set_liked(self,liked:bool):
        self._liked=liked; self._like_btn._icon="♥" if liked else "♡"
        self._like_btn._active=liked; self._like_btn.update(); self._exp.set_liked(liked)

    def get_volume(self)->int: return self._vol_slider.value()
    def focus_search(self): self._search_input.setFocus()

    def update_playlists(self,playlists:dict):
        # Remove all existing playlist buttons cleanly
        for btn in list(self._pl_btns.values()):
            btn.setParent(None); btn.deleteLater()
        self._pl_btns.clear()
        # Clear all items from layout (may have stretch + old buttons)
        while self._pl_vlay.count():
            item=self._pl_vlay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        # Re-add playlist buttons
        for pid,info in playlists.items():
            btn=GlassNavButton(f"  📋  {info.get('name','Untitled')}",self._pl_container)
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda _,p=pid:self._on_nav(f"playlist:{p}"))
            self._pl_vlay.addWidget(btn); self._pl_btns[pid]=btn
        self._pl_vlay.addStretch()
        # Force the scroll container to recalculate its size
        self._pl_container.adjustSize()
        self._pl_container.update()

    def set_search_loading(self,on:bool):
        self._search_btn.setText("…" if on else "Search")
        self._search_btn.setEnabled(not on); self._search_input.setEnabled(not on)

    def update_queue_display(self,tracks:list,current_idx:int):
        """Always store engine queue in overlay; re-render if open."""
        self._exp.update_queue(tracks, current_idx)

    def set_related_tracks(self,tracks:list):
        """Always store & render; shows skeleton if tracks is empty."""
        self._exp.set_related(tracks)

    def show_artist_profile(self,artist:str,tracks:list):
        self._artist_view.populate(artist,tracks)
        self._artist_view.setGeometry(self.SIDEBAR_W,0,self.width()-self.SIDEBAR_W,self.height()-self.PLAYERBAR_H)
        self._artist_view.show(); self._artist_view.raise_(); self._artist_view_active=True

    def show_playlist_picker(self,playlists:dict)->Optional[str]:
        modal=PlaylistPickerModal(playlists,self); modal.exec_()
        return modal.result_pid

    def show_new_playlist_modal(self)->Optional[str]:
        modal=NewPlaylistModal(self); modal.exec_()
        return modal.result_name

    def _on_new_playlist_btn(self):
        name=self.show_new_playlist_modal()
        if name: self.new_playlist_name_sig.emit(name)

    # ── Internal ───────────────────────────────────────────────────────────
    def _toggle_expanded(self):
        self._expanded=not self._expanded
        if self._expanded:
            self._exp.setGeometry(0,0,self.width(),self.height())
            self._exp.show_on_open()
            self._exp.show(); self._exp.raise_()
        else:
            self._exp.hide()

    def _on_artist_back(self): self._artist_view.hide(); self._artist_view_active=False
    def _on_artist_play(self,data:dict,idx:int): self.track_double_clicked.emit(data,idx)

    def _on_exp_loop(self,on:bool):
        self._looping=on; self._loop_btn.setActive(on); self.loop_sig.emit(on)

    def _on_exp_vol(self,vol:int):
        self._vol_slider.blockSignals(True); self._vol_slider.setValue(vol)
        self._vol_slider.blockSignals(False); self.volume_sig.emit(vol)

    def _on_vol(self,vol:int): self._exp.set_volume(vol); self.volume_sig.emit(vol)

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
        t=self._tracks[r]; artist=t.get("uploader") or t.get("channel","")
        menu=QMenu(self)
        menu.setStyleSheet("""
            QMenu{background:rgba(14,7,35,252);border:1px solid rgba(255,255,255,15);
                  border-radius:14px;padding:6px;color:white;}
            QMenu::item{padding:9px 22px;border-radius:8px;font-size:13px;}
            QMenu::item:selected{background:rgba(124,58,237,55);}
        """)
        for lbl,fn in [
            ("▶  Play now",           lambda:self.track_double_clicked.emit(t,r)),
            ("♥  Like",               lambda:self.like_track_sig.emit(t)),
            ("📋  Add to playlist",   lambda:self.add_to_playlist.emit(t)),
            ("🎤  Artist profile",    lambda:self.artist_search_sig.emit(artist)),
        ]:
            a=QAction(lbl,self); a.triggered.connect(fn); menu.addAction(a)
        menu.exec_(self._list.mapToGlobal(pos))

    def _on_seek(self,ratio:float):
        self._seeking=False
        if self._dur_ms>0: self.seek_sig.emit(int(ratio*self._dur_ms))

    def _on_loop(self):
        self._looping=not self._looping; self._loop_btn.setActive(self._looping)
        self._exp._looping=self._looping; self._exp._loop_btn.setActive(self._looping)
        self.loop_sig.emit(self._looping)
