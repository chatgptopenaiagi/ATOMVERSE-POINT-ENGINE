"""Observer-only signal projections; never writes to the entity or kernel."""
import math
from collections import deque
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter,QColor,QPen,QPainterPath
from PySide6.QtWidgets import QWidget
from .oscillator import signal

class SignalView(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.state={}; self.mode='wave'; self.trace=deque(maxlen=600); self.last=None
        self.setMinimumSize(560,420)
    def set_state(self,state):
        self.state=state
        key=(state.get('point_id'),state.get('tick'),state.get('state_version'))
        if key!=self.last:
            self.trace.append((state.get('oscillator_time',0),state.get('oscillator_value',0))); self.last=key
        self.update()
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.fillRect(self.rect(),QColor('#091522'))
        painter.setPen(QColor('#9db6c8')); painter.drawText(24,30,self.mode.upper()+' · perceptual projection of simulated state')
        s=self.state; amplitude=s.get('effective_amplitude',1); frequency=s.get('frequency',1); phase=s.get('phase',0); now=s.get('oscillator_time',0)
        painter.drawText(24,55,f'A {amplitude:.5f} dimensionless   f {frequency:.5f} cycles/sim s   phase {phase:.5f} rad')
        painter.drawText(24,self.height()-25,'Visualization observes state. Switching views never changes the entity.')
        if not s.get('entity_active',True): painter.drawText(24,90,'No active entity. Historical evidence is retained.'); return
        w,h=self.width()-80,self.height()-160; center=QPointF(self.width()/2,self.height()/2)
        painter.setPen(QPen(QColor('#254156'),1)); painter.drawLine(40,int(center.y()),self.width()-40,int(center.y()))
        path=QPainterPath()
        if self.mode=='spiral':
            for i in range(601):
                u=i/600; theta=phase+now*frequency*2*math.pi+u*6*math.pi
                radius=u*min(w,h)*.42
                point=QPointF(center.x()+radius*math.cos(theta),center.y()+radius*math.sin(theta))
                if i==0: path.moveTo(point)
                else: path.lineTo(point)
        elif self.mode=='signal':
            trace=list(self.trace)
            for i,(_,v) in enumerate(trace):
                point=QPointF(40+w*i/max(1,len(trace)-1),center.y()-v/max(1e-9,amplitude)*h*.4)
                if i==0: path.moveTo(point)
                else: path.lineTo(point)
        else:
            for i in range(601):
                t=now-2+4*i/600
                v=signal(amplitude,frequency,phase,t) if s.get('oscillator_enabled') else 0
                point=QPointF(40+w*i/600,center.y()-v/max(1e-9,amplitude)*h*.4)
                if i==0: path.moveTo(point)
                else: path.lineTo(point)
        painter.setPen(QPen(QColor('#76e6d4'),2)); painter.drawPath(path)
        painter.setPen(QColor('#f5c17e')); painter.drawText(24,82,f's(t) = {s.get("oscillator_value",0):.8f} · MATHEMATICAL SIMULATION')
