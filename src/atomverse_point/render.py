"""Native GPU OpenGL viewport. The camera cannot mutate the mathematical state."""
import math
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat, QPainter, QColor
from PySide6.QtOpenGL import QOpenGLFunctions_2_1
from PySide6.QtOpenGLWidgets import QOpenGLWidget

def surface_format():
    fmt=QSurfaceFormat(); fmt.setVersion(2,1); fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setDepthBufferSize(24); fmt.setSamples(4); fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)

class Viewport(QOpenGLWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setMinimumSize(560,420)
        self.state=None; self.wall_x=5.; self.grid=True; self.axes=True; self.wall=True
        self.yaw=-35.; self.pitch=25.; self.distance=22.; self.target=(0.,0.,0.)
        self.last_mouse=None; self.gl=None; self.gpu_info={}; self.frames=0; self.started=time.perf_counter()
        self.paint_ms=[]; self.trail=[]; self.last_version=-1; self.show_trail=True
        self.sphere_list=0; self.material_key=None
        self.mesh=[]
        for lat in range(20):
            strip=[]
            for lon in range(33):
                phi=2*math.pi*lon/32
                for k in (lat,lat+1):
                    theta=-math.pi/2+math.pi*k/20
                    normal=(math.cos(theta)*math.cos(phi),math.sin(theta),math.cos(theta)*math.sin(phi))
                    shade=.3+.7*max(0,(normal[0]*.3+normal[1]*.8+normal[2]*.5)/math.sqrt(.98))
                    strip.append((*normal,shade))
            self.mesh.append(strip)

    def initializeGL(self):
        self.gl=QOpenGLFunctions_2_1(); ok=self.gl.initializeOpenGLFunctions()
        if not ok: self.gpu_info={'error':'OpenGL 2.1 compatibility functions unavailable'}; return
        gl=self.gl
        self.sphere_list=gl.glGenLists(1)
        self.gpu_info={'vendor':gl.glGetString(0x1F00),'renderer':gl.glGetString(0x1F01),'version':gl.glGetString(0x1F02)}
        gl.glEnable(0x0B71) # depth test
        gl.glEnable(0x0BE2); gl.glBlendFunc(0x0302,0x0303)
        gl.glClearColor(.035,.055,.085,1.)

    def set_state(self,state,live=True):
        self.state=state
        if live and state['state_version']!=self.last_version:
            self.last_version=state['state_version']
            if not self.trail or tuple(state['position'])!=tuple(self.trail[-1]):
                self.trail.append(state['position'])
                if len(self.trail)>4000: del self.trail[:500]

    def line(self,a,b,color,width=1.):
        g=self.gl; g.glLineWidth(width); g.glColor4f(*color); g.glBegin(1)
        g.glVertex3f(*a); g.glVertex3f(*b); g.glEnd()

    def paintGL(self):
        started=time.perf_counter()
        g=self.gl
        if not g: return
        # QPainter changes OpenGL state. Re-establish it at every frame boundary.
        g.glEnable(0x0B71); g.glDepthMask(True); g.glDepthFunc(0x0203)
        g.glEnable(0x0BE2); g.glBlendFunc(0x0302,0x0303)
        g.glClear(0x00004000|0x00000100)
        g.glViewport(0,0,int(self.width()*self.devicePixelRatioF()),int(self.height()*self.devicePixelRatioF()))
        g.glMatrixMode(0x1701); g.glLoadIdentity()
        near=.05; top=near*math.tan(math.radians(45)/2); aspect=self.width()/max(1,self.height())
        g.glFrustum(-top*aspect,top*aspect,-top,top,near,max(10000,self.distance*4))
        g.glMatrixMode(0x1700); g.glLoadIdentity()
        g.glTranslated(0,0,-self.distance); g.glRotated(self.pitch,1,0,0); g.glRotated(self.yaw,0,1,0)
        g.glTranslated(*(-x for x in self.target))
        if self.grid:
            for i in range(-20,21):
                self.line((i,-2,-20),(i,-2,20),(.13,.2,.28,.8))
                self.line((-20,-2,i),(20,-2,i),(.13,.2,.28,.8))
        if self.axes:
            self.line((-15,0,0),(15,0,0),(.95,.27,.3,1),2)
            self.line((0,-15,0),(0,15,0),(.3,.85,.5,1),2)
            self.line((0,0,-15),(0,0,15),(.3,.55,1,1),2)
        if self.show_trail and self.trail:
            g.glLineWidth(1.5); g.glColor4f(.3,.8,.9,.55); g.glBegin(3)
            for p in self.trail: g.glVertex3d(*p)
            g.glEnd()
        if self.state and self.state.get('entity_active',True):
            s=self.state; p=s['position']; r=s['radius']; color=s['color']; representation=s['representation']
            g.glPushMatrix(); g.glTranslated(*p)
            if representation!='center':
                if representation=='wireframe': g.glPolygonMode(0x0408,0x1B01)
                g.glEnable(0x0B44); g.glCullFace(0x0405)
                alpha=min(color[3],.35) if representation=='transparent' else color[3]
                key=(tuple(color),representation,s['intensity'])
                if key!=self.material_key:
                    g.glNewList(self.sphere_list,0x1300)
                    for strip in self.mesh:
                        g.glBegin(5)
                        for x,y,z,shade in strip:
                            light=1. if representation=='luminous' else shade
                            g.glColor4f(*(min(1,c*light*s['intensity']) for c in color[:3]),alpha)
                            g.glVertex3d(x,y,z)
                        g.glEnd()
                    g.glEndList(); self.material_key=key
                g.glPushMatrix(); g.glScaled(r,r,r); g.glCallList(self.sphere_list); g.glPopMatrix()
                g.glDisable(0x0B44); g.glPolygonMode(0x0408,0x1B02)
            g.glDisable(0x0B71)
            for axis in range(3):
                a=[0.,0.,0.]; b=[0.,0.,0.]; a[axis]=-.12; b[axis]=.12
                self.line(a,b,(1.,1.,1.,.9),2)
            g.glEnable(0x0B71); g.glPopMatrix()
        if self.wall:
            g.glDepthMask(False); g.glColor4f(.95,.6,.2,.16); g.glBegin(7)
            for y,z in [(-2,-8),(8,-8),(8,8),(-2,8)]: g.glVertex3f(self.wall_x,y,z)
            g.glEnd(); g.glDepthMask(True)
            for z in range(-8,9,2): self.line((self.wall_x,-2,z),(self.wall_x,8,z),(.9,.6,.25,.25))
        # Native overlay clearly identifies the camera, axes and idealized plane.
        painter=QPainter(self); painter.setPen(QColor('#a8bacb'))
        painter.drawText(18,28,'ONE POINT  /  drag to orbit · wheel to zoom · focus to follow')
        painter.drawText(18,self.height()-20,'X red   Y green   Z blue    |    wall: infinite plane X = '+str(self.wall_x))
        painter.end()
        self.frames+=1; self.paint_ms.append((time.perf_counter()-started)*1000)
        if len(self.paint_ms)>600: self.paint_ms.pop(0)

    def mousePressEvent(self,event): self.last_mouse=event.position()
    def mouseMoveEvent(self,event):
        if self.last_mouse is not None and event.buttons() & Qt.LeftButton:
            delta=event.position()-self.last_mouse; self.yaw+=delta.x()*.4
            self.pitch=max(-89,min(89,self.pitch+delta.y()*.4)); self.last_mouse=event.position(); self.update()
    def mouseReleaseEvent(self,event): self.last_mouse=None
    def wheelEvent(self,event):
        self.distance=max(.2,min(1e10,self.distance*math.exp(-event.angleDelta().y()/1200))); self.update()

    def stats(self):
        return {'graphics':self.gpu_info,'frames':self.frames,'average_fps':self.frames/max(.001,time.perf_counter()-self.started),
                'mean_cpu_paint_ms':sum(self.paint_ms)/max(1,len(self.paint_ms))}
