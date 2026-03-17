"""ui/player_bar.py — Premium glass player bar."""
import threading
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt5.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor, QBrush, QPen,
    QLinearGradient, QRadialGradient,
)
import requests


def _ms(ms):
    s=ms//1000; m,s=divmod(s,60)
    return f"{m}:{s:02d}"


class ThumbLabel(QLabel):
    def __init__(self):
        super().__init__(); self._pix=None; self.setFixedSize(58,58)
    def set_url(self,url):
        threading.Thread(target=self._fetch,args=(url,),daemon=True).start()
    def _fetch(self,url):
        try:
            r=requests.get(url,timeout=5); p=QPixmap(); p.loadFromData(r.content)
            self._pix=p
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
            p.fillPath(path,QBrush(QColor(45,18,85)))
            p.setPen(QColor(180,120,255,180))
            f=p.font(); f.setPointSize(22); p.setFont(f)
            p.drawText(self.rect(),Qt.AlignCenter,"♪")
        # Subtle border
        p.setClipping(False)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255,255,255,20),1))
        p.drawRoundedRect(QRectF(0.5,0.5,self.width()-1,self.height()-1),12,12)
        p.end()


class GlowButton(QPushButton):
    """Circle button with glow effect."""
    def __init__(self, icon, sz=40, accent=False, toggle=False, parent=None):
        super().__init__(parent)
        self._icon=icon; self._sz=sz; self._accent=accent
        self._toggle=toggle; self._active=False; self._hov=False
        self.setFixedSize(sz,sz); self.setCursor(Qt.PointingHandCursor); self.setFlat(True)

    def setActive(self,on): self._active=on; self.update()
    def enterEvent(self,e): self._hov=True; self.update()
    def leaveEvent(self,e): self._hov=False; self.update()

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect(); cx=r.width()/2; cy=r.height()/2; rad=min(cx,cy)-1

        if self._accent:
            # Glowing gradient circle
            g=QLinearGradient(0,0,r.width(),r.height())
            if self._hov:
                g.setColorAt(0,QColor(168,85,247)); g.setColorAt(1,QColor(236,72,153))
            else:
                g.setColorAt(0,QColor(124,58,237)); g.setColorAt(1,QColor(219,39,119))
            p.setBrush(QBrush(g)); p.setPen(Qt.NoPen)
            p.drawEllipse(r.adjusted(2,2,-2,-2))
            # Outer glow ring
            glow=QRadialGradient(cx,cy,rad+8)
            glow.setColorAt(0, QColor(147,51,234,0))
            glow.setColorAt(0.7,QColor(147,51,234,0))
            glow.setColorAt(1.0,QColor(147,51,234,50 if self._hov else 25))
            p.setBrush(QBrush(glow)); p.setPen(Qt.NoPen)
            p.drawEllipse(r)
            # Inner highlight
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255,255,255,40),1))
            p.drawEllipse(r.adjusted(3,3,-3,-3))
        elif self._active:
            p.setBrush(QBrush(QColor(124,58,237,55)))
            p.setPen(QPen(QColor(167,139,250,120),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        elif self._hov:
            p.setBrush(QBrush(QColor(255,255,255,14)))
            p.setPen(QPen(QColor(255,255,255,28),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))
        else:
            p.setBrush(QBrush(QColor(255,255,255,7)))
            p.setPen(QPen(QColor(255,255,255,16),1))
            p.drawEllipse(r.adjusted(2,2,-2,-2))

        # Icon
        if self._accent: p.setPen(QColor(255,255,255,240))
        elif self._active: p.setPen(QColor(167,139,250,255))
        elif self._hov: p.setPen(QColor(255,255,255,220))
        else: p.setPen(QColor(255,255,255,160))
        f=p.font(); f.setPointSize(max(8,int(self._sz*0.28))); p.setFont(f)
        p.drawText(r,Qt.AlignCenter,self._icon)
        p.end()


class GlassSeekBar(QWidget):
    seek_pressed=pyqtSignal()
    seek_released=pyqtSignal(float)  # 0.0-1.0

    def __init__(self,parent=None):
        super().__init__(parent)
        self._val=0.0; self._drag=False
        self.setFixedHeight(20); self.setCursor(Qt.PointingHandCursor)

    def set_value(self,v): self._val=max(0.0,min(1.0,v)); self.update()

    def mousePressEvent(self,e):
        self._drag=True; self._update_from_mouse(e.x()); self.seek_pressed.emit()
    def mouseMoveEvent(self,e):
        if self._drag: self._update_from_mouse(e.x())
    def mouseReleaseEvent(self,e):
        self._drag=False; self._update_from_mouse(e.x()); self.seek_released.emit(self._val)
    def _update_from_mouse(self,x):
        pad=8; w=self.width()-pad*2
        self._val=max(0.0,min(1.0,(x-pad)/max(1,w))); self.update()

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w=self.width(); cy=self.height()//2; pad=8; track_h=3

        # Background
        p.setBrush(QBrush(QColor(255,255,255,18))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(pad,cy-track_h//2,w-pad*2,track_h,2,2)

        # Fill
        fill=int((w-pad*2)*self._val)
        if fill>0:
            g=QLinearGradient(pad,0,pad+fill,0)
            g.setColorAt(0,QColor(124,58,237)); g.setColorAt(1,QColor(219,39,119))
            p.setBrush(QBrush(g)); p.drawRoundedRect(pad,cy-track_h//2,fill,track_h,2,2)

        # Handle
        hx=pad+fill
        # Glow
        glow=QRadialGradient(hx,cy,10)
        glow.setColorAt(0,QColor(167,139,250,80)); glow.setColorAt(1,QColor(0,0,0,0))
        p.setBrush(QBrush(glow)); p.setPen(Qt.NoPen); p.drawEllipse(hx-10,cy-10,20,20)
        # Dot
        p.setBrush(QBrush(QColor(255,255,255))); p.setPen(QPen(QColor(147,51,234,200),1.5))
        p.drawEllipse(hx-5,cy-5,10,10)
        p.end()


class PlayerBar(QWidget):
    play_pause_clicked=pyqtSignal()
    prev_clicked=pyqtSignal()
    next_clicked=pyqtSignal()
    stop_clicked=pyqtSignal()
    seek_requested=pyqtSignal(int)
    volume_changed=pyqtSignal(int)
    like_clicked=pyqtSignal()
    loop_toggled=pyqtSignal(bool)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("playerPanel")
        self.setFixedHeight(100)
        self._dur_ms=0; self._seeking=False; self._liked=False; self._looping=False
        self._build()

    def _build(self):
        root=QHBoxLayout(self); root.setContentsMargins(24,0,24,0); root.setSpacing(0)

        # LEFT — thumb + info + like
        left=QHBoxLayout(); left.setSpacing(14); left.setContentsMargins(0,0,0,0)
        self._thumb=ThumbLabel(); left.addWidget(self._thumb)
        info=QVBoxLayout(); info.setSpacing(3); info.setContentsMargins(0,0,0,0)
        self._title=QLabel("Nothing playing"); self._title.setObjectName("trackTitle"); self._title.setMaximumWidth(180)
        self._artist=QLabel("—"); self._artist.setObjectName("trackArtist")
        info.addWidget(self._title); info.addWidget(self._artist)
        left.addLayout(info)
        self._like=GlowButton("♡",32); self._like.clicked.connect(self._on_like)
        left.addSpacing(8); left.addWidget(self._like)
        lw=QWidget(); lw.setLayout(left); lw.setFixedWidth(300); root.addWidget(lw)

        # CENTRE — controls + seek
        centre=QVBoxLayout(); centre.setSpacing(10); centre.setContentsMargins(0,12,0,10); centre.setAlignment(Qt.AlignVCenter)

        btns=QHBoxLayout(); btns.setSpacing(10); btns.setAlignment(Qt.AlignCenter)
        self._loop=GlowButton("⟳",36,toggle=True); self._loop.clicked.connect(self._on_loop)
        self._prev=GlowButton("⏮",42); self._prev.clicked.connect(self.prev_clicked)
        self._play=GlowButton("▶",58,accent=True); self._play.clicked.connect(self.play_pause_clicked)
        self._next=GlowButton("⏭",42); self._next.clicked.connect(self.next_clicked)
        self._stop=GlowButton("⏹",36); self._stop.clicked.connect(self.stop_clicked)
        for w in(self._loop,self._prev,self._play,self._next,self._stop): btns.addWidget(w)
        centre.addLayout(btns)

        seek_row=QHBoxLayout(); seek_row.setSpacing(10); seek_row.setContentsMargins(0,0,0,0)
        self._pos_lbl=QLabel("0:00"); self._pos_lbl.setObjectName("timeLabel"); self._pos_lbl.setFixedWidth(36); self._pos_lbl.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self._seek=GlassSeekBar()
        self._seek.seek_pressed.connect(lambda:setattr(self,"_seeking",True))
        self._seek.seek_released.connect(self._on_seek)
        self._dur_lbl=QLabel("0:00"); self._dur_lbl.setObjectName("timeLabel"); self._dur_lbl.setFixedWidth(36)
        seek_row.addWidget(self._pos_lbl); seek_row.addWidget(self._seek,1); seek_row.addWidget(self._dur_lbl)
        centre.addLayout(seek_row)
        root.addLayout(centre,1)

        # RIGHT — volume
        vr=QHBoxLayout(); vr.setSpacing(8); vr.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        vi=QLabel("🔊"); vi.setStyleSheet("font-size:14px; color:rgba(255,255,255,130);")
        self._vol=QSlider(Qt.Horizontal); self._vol.setObjectName("volSlider")
        self._vol.setRange(0,100); self._vol.setValue(70); self._vol.setFixedWidth(90)
        self._vol.setCursor(Qt.PointingHandCursor); self._vol.valueChanged.connect(self.volume_changed)
        vr.addWidget(vi); vr.addWidget(self._vol)
        rw=QWidget(); rw.setLayout(vr); rw.setFixedWidth(160); root.addWidget(rw)

    # Public
    def set_track(self,title,artist):
        self._title.setText((title[:28]+"…") if len(title)>28 else title); self._artist.setText(artist)
    def set_thumbnail(self,url): self._thumb.set_url(url)
    def set_playing(self,playing): self._play._icon="⏸" if playing else "▶"; self._play.update()
    def set_position(self,ms):
        if self._seeking: return
        self._pos_lbl.setText(_ms(ms))
        if self._dur_ms>0: self._seek.set_value(ms/self._dur_ms)
    def set_duration(self,ms): self._dur_ms=ms; self._dur_lbl.setText(_ms(ms))
    def set_liked(self,liked):
        self._liked=liked; self._like._icon="♥" if liked else "♡"
        self._like._active=liked; self._like.update()
    def get_volume(self): return self._vol.value()
    def is_looping(self): return self._looping
    def _on_seek(self,ratio):
        self._seeking=False
        if self._dur_ms>0: self.seek_requested.emit(int(ratio*self._dur_ms))
    def _on_like(self): self.like_clicked.emit()
    def _on_loop(self):
        self._looping=not self._looping; self._loop.setActive(self._looping); self.loop_toggled.emit(self._looping)

    def paintEvent(self,e):
        p=QPainter(self)
        g=QLinearGradient(0,0,self.width(),0)
        g.setColorAt(0.0, QColor(6,2,18,160))
        g.setColorAt(0.5, QColor(8,3,22,150))
        g.setColorAt(1.0, QColor(6,2,18,160))
        p.fillRect(self.rect(),g)
        p.setPen(QPen(QColor(255,255,255,12),1))
        p.drawLine(0,0,self.width(),0)
        p.end()
        super().paintEvent(e)
