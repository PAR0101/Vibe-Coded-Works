"""ui/track_list.py — Premium glass track rows."""
import threading
from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QLabel,
    QHBoxLayout, QVBoxLayout, QAbstractItemView, QMenu, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, pyqtSlot
from PyQt5.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor,
    QBrush, QPen, QLinearGradient,
)
import requests


class MiniThumb(QLabel):
    def __init__(self):
        super().__init__(); self._pix=None; self.setFixedSize(46,34)
    def set_url(self, url):
        threading.Thread(target=self._fetch, args=(url,), daemon=True).start()
    def _fetch(self, url):
        try:
            r=requests.get(url,timeout=4); p=QPixmap(); p.loadFromData(r.content)
            self._pix=p
            from PyQt5.QtCore import QMetaObject, Qt as Q
            QMetaObject.invokeMethod(self,'_apply',Q.QueuedConnection)
        except: pass
    @pyqtSlot()
    def _apply(self): self.update()
    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        path=QPainterPath(); path.addRoundedRect(0,0,self.width(),self.height(),6,6)
        p.setClipPath(path)
        if self._pix:
            s=self._pix.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(0,0,s)
        else:
            p.fillPath(path,QBrush(QColor(50,22,90)))
            p.setPen(QColor(160,100,230,140)); p.drawText(self.rect(),Qt.AlignCenter,"♪")
        p.end()


class TrackRow(QWidget):
    def __init__(self, data, idx, parent=None):
        super().__init__(parent); self.data=data; self.idx=idx
        self._hi=False; self._hover=False; self._build()
        self.setMouseTracking(True)

    def _build(self):
        lay=QHBoxLayout(self); lay.setContentsMargins(12,8,18,8); lay.setSpacing(14)

        # Index
        n=QLabel(str(self.idx+1))
        n.setFixedWidth(28); n.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        n.setStyleSheet("color:rgba(255,255,255,50); font-size:11px; font-weight:500;")
        lay.addWidget(n)

        # Thumbnail
        self._thumb=MiniThumb()
        url=self.data.get("thumbnail","")
        if url: self._thumb.set_url(url)
        lay.addWidget(self._thumb)

        # Title + artist
        info=QVBoxLayout(); info.setSpacing(3); info.setContentsMargins(0,0,0,0)
        title=self.data.get("title","Unknown")
        artist=self.data.get("uploader") or self.data.get("channel","")
        tl=QLabel((title[:60]+"…") if len(title)>60 else title)
        tl.setStyleSheet("color:rgba(255,255,255,220); font-size:13px; font-weight:500;")
        al=QLabel((artist[:50]) if artist else "")
        al.setStyleSheet("color:rgba(255,255,255,110); font-size:11px;")
        info.addWidget(tl); info.addWidget(al)
        lay.addLayout(info,1)

        # Duration
        dur=int(self.data.get("duration") or 0)
        m,s=divmod(dur,60); h,m=divmod(m,60)
        ds=f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        dl=QLabel(ds)
        dl.setStyleSheet("color:rgba(255,255,255,90); font-size:12px;")
        dl.setFixedWidth(48); dl.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        lay.addWidget(dl)

    def set_highlight(self, on): self._hi=on; self.update()
    def enterEvent(self, e): self._hover=True; self.update()
    def leaveEvent(self, e): self._hover=False; self.update()

    def paintEvent(self, e):
        if self._hi or self._hover:
            p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            if self._hi:
                g=QLinearGradient(0,0,self.width(),0)
                g.setColorAt(0, QColor(124,58,237,28))
                g.setColorAt(0.5,QColor(219,39,119,15))
                g.setColorAt(1, QColor(124,58,237,10))
                p.setBrush(QBrush(g))
                p.setPen(QPen(QColor(147,51,234,35),1))
            else:
                p.setBrush(QBrush(QColor(255,255,255,5)))
                p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),10,10)
            p.end()
        super().paintEvent(e)


class TrackList(QWidget):
    track_activated=pyqtSignal(dict,int)
    add_to_queue=pyqtSignal(dict)
    add_to_playlist=pyqtSignal(dict)
    like_track=pyqtSignal(dict)

    def __init__(self,parent=None):
        super().__init__(parent); self._data=[]; self._cur=-1; self._build()

    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self._list=QListWidget()
        self._list.setSpacing(2)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(self._dbl)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx)
        lay.addWidget(self._list)

    def set_tracks(self,tracks):
        self._data=tracks; self._list.clear()
        for i,t in enumerate(tracks):
            item=QListWidgetItem(self._list)
            row=TrackRow(t,i)
            item.setSizeHint(QSize(0,60))
            self._list.addItem(item)
            self._list.setItemWidget(item,row)

    def set_current_index(self,idx):
        prev=self._cur; self._cur=idx
        for i in (prev,idx):
            if 0<=i<self._list.count():
                w=self._list.itemWidget(self._list.item(i))
                if isinstance(w,TrackRow): w.set_highlight(i==idx)
        if 0<=idx<self._list.count():
            self._list.scrollToItem(self._list.item(idx),QAbstractItemView.PositionAtCenter)

    def clear(self): self._data=[]; self._list.clear()

    def _dbl(self,item):
        r=self._list.row(item)
        if 0<=r<len(self._data): self.track_activated.emit(self._data[r],r)

    def _ctx(self,pos):
        item=self._list.itemAt(pos)
        if not item: return
        r=self._list.row(item)
        if r<0 or r>=len(self._data): return
        t=self._data[r]
        menu=QMenu(self)
        menu.setStyleSheet("""
            QMenu{background:rgba(14,7,35,252);border:1px solid rgba(255,255,255,12);
                  border-radius:14px;padding:6px;}
            QMenu::item{padding:9px 22px;color:white;border-radius:8px;font-size:13px;}
            QMenu::item:selected{background:rgba(124,58,237,50);}
        """)
        for label,fn in [
            ("▶  Play now",        lambda:self.track_activated.emit(t,r)),
            ("➕  Add to queue",   lambda:self.add_to_queue.emit(t)),
            ("♥  Like",            lambda:self.like_track.emit(t)),
            ("📋  Add to playlist", lambda:self.add_to_playlist.emit(t)),
        ]:
            a=QAction(label,self); a.triggered.connect(fn); menu.addAction(a)
        menu.exec_(self._list.mapToGlobal(pos))
