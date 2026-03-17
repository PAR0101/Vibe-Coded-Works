"""
ui/lava_lamp.py — Premium lava lamp background.
Rich particle field + large flowing gradient orbs.
"""
import math, random
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import (
    QPainter, QRadialGradient, QColor, QPainterPath,
    QLinearGradient, QBrush, QPen, QConicalGradient,
)


class Orb:
    """Large slow-moving glowing orb."""
    PALETTES = [
        [(130,20,220),(180,40,255)],   # purple
        [(210,20,130),(255,60,180)],   # pink/magenta
        [(20,60,200),(60,120,255)],    # blue
        [(180,60,10),(240,120,30)],    # orange
        [(100,10,180),(160,40,230)],   # violet
    ]
    def __init__(self, w, h, idx):
        self.w=w; self.h=h
        self.pal = self.PALETTES[idx % len(self.PALETTES)]
        self.x = random.uniform(0.1,0.9)*w
        self.y = random.uniform(0.1,0.9)*h
        spd = random.uniform(0.12,0.35)
        ang = random.uniform(0,2*math.pi)
        self.vx=math.cos(ang)*spd; self.vy=math.sin(ang)*spd
        self.base_r = random.uniform(0.18,0.34)*min(w,h)
        self.r=self.base_r; self.t=random.uniform(0,200)
        self.ps=random.uniform(0.004,0.012); self.pp=random.uniform(0,6.28)
        self.wf=[random.uniform(1.5,4) for _ in range(5)]
        self.wa=[random.uniform(0.04,0.13)*self.base_r for _ in range(5)]
        self.wp=[random.uniform(0,6.28) for _ in range(5)]
        self.ws=[random.uniform(0.006,0.02) for _ in range(5)]

    def update(self):
        self.t+=1
        self.x+=self.vx; self.y+=self.vy
        pad=self.base_r*1.1
        if self.x<pad or self.x>self.w-pad: self.vx*=-1; self.x=max(pad,min(self.w-pad,self.x))
        if self.y<pad or self.y>self.h-pad: self.vy*=-1; self.y=max(pad,min(self.h-pad,self.y))
        self.r=self.base_r*(1+0.12*math.sin(self.t*self.ps+self.pp))
        for i in range(5): self.wp[i]+=self.ws[i]

    def path(self):
        N=48; pts=[]
        for i in range(N):
            theta=2*math.pi*i/N; r=self.r
            for f,a,p in zip(self.wf,self.wa,self.wp): r+=a*math.sin(f*theta+p)
            pts.append(QPointF(self.x+r*math.cos(theta),self.y+r*math.sin(theta)))
        path=QPainterPath(); path.moveTo(pts[0])
        for i in range(N):
            p0=pts[i]; p1=pts[(i+1)%N]; p2=pts[(i+2)%N]; pm=pts[(i-1)%N]
            path.cubicTo(p0.x()+(p1.x()-pm.x())/6,p0.y()+(p1.y()-pm.y())/6,
                         p1.x()-(p2.x()-p0.x())/6,p1.y()-(p2.y()-p0.y())/6,p1.x(),p1.y())
        path.closeSubpath(); return path

    def gradient(self):
        r1,g1,b1=self.pal[0]; r2,g2,b2=self.pal[1]
        g=QRadialGradient(self.x,self.y,self.r*1.5)
        g.setColorAt(0.0, QColor(r2,g2,b2,200))
        g.setColorAt(0.35,QColor(r1,g1,b1,150))
        g.setColorAt(0.7, QColor(r1//2,g1//2,b1//2,80))
        g.setColorAt(1.0, QColor(0,0,0,0))
        return g


class Particle:
    """Tiny floating sparkle particle."""
    def __init__(self, w, h):
        self.w=w; self.h=h; self.reset()
    def reset(self):
        self.x=random.uniform(0,self.w); self.y=random.uniform(0,self.h)
        self.vx=random.uniform(-0.3,0.3); self.vy=random.uniform(-0.5,-0.1)
        self.r=random.uniform(1,3); self.life=random.uniform(0,1)
        self.decay=random.uniform(0.002,0.006)
        c=random.choice([(180,100,255),(255,100,200),(100,150,255),(255,160,80)])
        self.color=c; self.alpha=int(random.uniform(100,200))
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.life-=self.decay
        if self.life<=0 or self.x<0 or self.x>self.w or self.y<0: self.reset(); self.life=1.0


class LavaLampWidget(QWidget):
    FPS=30; N_ORBS=8; N_PARTICLES=60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)
        self._orbs=[]; self._particles=[]
        self._t=QTimer(self); self._t.timeout.connect(self._tick); self._t.start(1000//self.FPS)
        self._init()

    def _init(self):
        w=max(self.width(),1000); h=max(self.height(),700)
        self._orbs=[Orb(w,h,i) for i in range(self.N_ORBS)]
        self._particles=[Particle(w,h) for _ in range(self.N_PARTICLES)]

    def resizeEvent(self,e): super().resizeEvent(e); self._init()
    def _tick(self):
        for o in self._orbs: o.update()
        for p in self._particles: p.update()
        self.update()

    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()

        # Rich deep background — diagonal gradient
        bg=QLinearGradient(0,0,w,h)
        bg.setColorAt(0.0, QColor(8,3,20))
        bg.setColorAt(0.3, QColor(18,6,40))
        bg.setColorAt(0.6, QColor(12,4,30))
        bg.setColorAt(1.0, QColor(5,2,14))
        p.fillRect(0,0,w,h,bg)

        # Secondary colour wash (adds warmth to one corner)
        warm=QRadialGradient(w*0.8,h*0.7,h*0.7)
        warm.setColorAt(0.0, QColor(180,50,10,60))
        warm.setColorAt(1.0, QColor(0,0,0,0))
        p.fillRect(0,0,w,h,warm)

        # Orbs — additive blending creates the glow
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for o in self._orbs:
            p.setBrush(QBrush(o.gradient())); p.setPen(Qt.NoPen)
            p.drawPath(o.path())

        # Particles
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for pt in self._particles:
            alpha=int(pt.alpha*pt.life)
            r,g,b=pt.color
            p.setBrush(QBrush(QColor(r,g,b,alpha))); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(pt.x,pt.y), pt.r, pt.r)

        # Vignette — pull edges to black for depth
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        vig=QRadialGradient(w/2,h/2,max(w,h)*0.72)
        vig.setColorAt(0.3, QColor(0,0,0,0))
        vig.setColorAt(0.75,QColor(0,0,0,80))
        vig.setColorAt(1.0, QColor(0,0,0,200))
        p.fillRect(0,0,w,h,vig)

        # Subtle top-edge light leak
        leak=QLinearGradient(0,0,0,120)
        leak.setColorAt(0.0, QColor(200,100,255,30))
        leak.setColorAt(1.0, QColor(0,0,0,0))
        p.fillRect(0,0,w,120,leak)

        p.end()
