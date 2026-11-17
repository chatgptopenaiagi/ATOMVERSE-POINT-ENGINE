"""Deterministic fixed-step single-point kernel; no GUI, database or model calls."""
from __future__ import annotations
import copy
import math
import time
import uuid
from .model import PointState, Expression, number, vector, validate_command
from .oscillator import signal,map_amplitude

def add(a,b): return tuple(x+y for x,y in zip(a,b))

class Path:
    def __init__(self, spec, origin):
        self.spec, self.origin = spec, origin
        self.expressions = [Expression(x) for x in spec.get('expressions',[])]

    def position(self,t):
        s, p = self.spec, self.origin
        kind, duration = s['kind'], s['duration']
        if kind == 'line': return tuple(x+(y-x)*t/duration for x,y in zip(p,s['target']))
        if kind == 'polyline':
            # Equal duration per segment, including current position -> first vertex.
            points = [p]+s['points']
            u = min(len(points)-1,max(0,t/duration*(len(points)-1)))
            i = min(len(points)-2,int(u)); f=u-i
            return tuple(a+(b-a)*f for a,b in zip(points[i],points[i+1]))
        if kind == 'custom': return add(p,tuple(e(t)-e(0) for e in self.expressions))
        phase = s['phase']; angle=phase+2*math.pi*s['frequency']*t
        a=s['amplitude']; r=a+(s['growth']*t if kind=='spiral' else 0)
        return add(p,(r*math.cos(angle)-a*math.cos(phase),r*math.sin(angle)-a*math.sin(phase),s['pitch']*t if kind=='helix' else 0))

    def velocity(self,t):
        h=1e-5
        return tuple((b-a)/(2*h) for a,b in zip(self.position(t-h),self.position(t+h)))

class Kernel:
    def __init__(self, sim_hz=240, point_id=None):
        self.hz = int(number(sim_hz,1,2000))
        self.dt = 1/self.hz
        self.state = PointState()
        if point_id: self.state.point_id=point_id
        self.initial = self.state.position
        self.wall_x=5.
        self.restitution=1.
        self.pending=[]
        self.projections={}
        self.active=None
        self.path=None
        self.path_elapsed=0.
        self.events=[]
        self.resume_status='STOPPED'
        self.telemetry=None
        self.recent_events=[]

    def emit(self,kind,payload):
        self.events.append({'kind':kind,'tick':self.state.tick,'sim_time':self.state.sim_time,
                            'utc_ns':time.time_ns(),'monotonic_ns':time.perf_counter_ns(),'payload':copy.deepcopy(payload)})
        self.recent_events.append({'kind':kind,'tick':self.state.tick,'sim_time':self.state.sim_time})
        if len(self.recent_events)>32: self.recent_events.pop(0)

    def observe_telemetry(self,measurement):
        """Called only by the optional collector boundary; never a model command."""
        if not isinstance(measurement,dict) or measurement.get('classification') not in ('OBSERVED_TELEMETRY','CONTROLLED_TEST'):
            raise ValueError('Telemetry provenance is required')
        values=measurement.get('values',{})
        if not isinstance(values,dict) or len(values)>16: raise ValueError('Invalid telemetry packet')
        from .model import METRICS
        clean={k:number(v,0,1e9) for k,v in values.items() if k in METRICS}
        self.telemetry=dict(measurement,values=clean)
        self.emit('telemetry',self.telemetry)

    def update_oscillator(self):
        s=self.state; effective=s.amplitude; status='DISABLED'
        if s.telemetry_mapping['enabled']:
            metric=s.telemetry_mapping['metric']
            if self.telemetry and self.telemetry.get('fresh',False) and metric in self.telemetry['values']:
                effective=map_amplitude(self.telemetry['values'][metric],s.telemetry_mapping)['value']; status='MAPPED'
            else: status='UNAVAILABLE / MANUAL AMPLITUDE'
        s.effective_amplitude=effective
        if status!=s.telemetry_status:
            s.telemetry_status=status
            self.emit('mapping_status',{'status':status,'effective_amplitude':effective,'classification':'DERIVED_COMPUTATION'})
        s.oscillator_value=signal(effective,s.frequency,s.phase,s.oscillator_time) if s.oscillator_enabled else 0.

    def drain_events(self):
        events,self.events=self.events,[]
        return events

    def transition(self,identifier,status,reason=None):
        if identifier is None: return
        self.projections[identifier]['status']=status
        self.emit('projection',{'command_id':identifier,'status':status,'reason':reason,'state':self.state.snapshot()})

    def cancel_active(self):
        self.transition(self.active,'CANCELLED','superseded by operator or collision')
        self.active=None; self.path=None

    def submit(self,raw):
        c=validate_command(raw)
        if c['action']=='create' and 'entity_id' not in c: c['entity_id']=str(uuid.uuid4())
        if c.get('at',self.state.sim_time)>self.state.sim_time+1e-12 and len(self.pending)>=1024:
            raise ValueError('Scheduled command capacity reached')
        identifier=str(uuid.uuid4())
        self.projections[identifier]={'command':c,'status':'CREATED'}
        self.emit('command',{'command_id':identifier,'command':c,'status':'CREATED'})
        if c.get('at',self.state.sim_time)>self.state.sim_time+1e-12:
            self.pending.append((c['at'],identifier,c))
            self.pending.sort(key=lambda x:x[0])
            self.transition(identifier,'SCHEDULED')
        else: self.execute(identifier,c)
        # Completed commands live in history; cap the diagnostic lookup.
        if len(self.projections)>2048:
            for key in list(self.projections):
                if self.projections[key]['status'] in ('COMPLETED','FAILED','CANCELLED'):
                    del self.projections[key]
                    if len(self.projections)<=1024: break
        return identifier

    def execute(self,identifier,c):
        self.transition(identifier,'ACTIVE')
        s=self.state; action=c['action']; ongoing=False
        try:
            # State-dependent validation precedes any cancellation or mutation.
            if action=='translate': vector(add(s.position,c['delta']))
            if not s.entity_active and action not in ('create','restore'): raise ValueError('No active entity; create or restore one first')
            if action=='create':
                if s.entity_active: raise ValueError('Exactly one active entity is allowed; delete first')
                self.state=PointState(point_id=c['entity_id'],tick=s.tick,sim_time=s.sim_time,state_version=s.state_version+1)
                s=self.state; self.initial=s.position; self.telemetry=None; self.resume_status='STOPPED'
            elif action=='delete':
                self.cancel_active()
                for _,pid,_ in self.pending: self.transition(pid,'CANCELLED','entity deleted')
                self.pending=[]; s.entity_active=False; s.simulation_status='DELETED'; s.velocity=(0.,)*3; s.oscillator_enabled=False
            elif action=='restore':
                restored=c['state']; self.cancel_active()
                for _,pid,_ in self.pending: self.transition(pid,'CANCELLED','state restored')
                self.pending=[]
                for key in ('point_id','position','radius','color','velocity','acceleration','intensity','representation','collision_mode','frequency','amplitude','phase','oscillator_enabled','oscillator_time','information_state'):
                    setattr(s,key,copy.deepcopy(restored[key]))
                s.entity_active=True; s.simulation_status='PAUSED'; s.movement_mode='velocity'; self.resume_status='RUNNING' if any(s.velocity) or any(s.acceleration) else 'STOPPED'
                s.telemetry_mapping=dict(restored['telemetry_mapping'],enabled=False)
                self.emit('restored',{'source_entity_id':restored['point_id'],'source_tick':restored['tick'],'source_sim_time':restored['sim_time'],'clock_policy':'current timeline retained; restored point paused; hardware mapping disabled'})
            elif action=='oscillator':
                for key in ('frequency','amplitude','phase'):
                    if key in c: setattr(s,key,c[key])
                if 'enabled' in c: s.oscillator_enabled=c['enabled']
                self.emit('oscillator_configuration',{'frequency':s.frequency,'amplitude':s.amplitude,'phase':s.phase,'enabled':s.oscillator_enabled,'classification':'MATHEMATICAL_SIMULATION'})
            elif action=='information': s.information_state=copy.deepcopy(c['information_state'])
            elif action=='mapping':
                s.telemetry_mapping={k:v for k,v in c.items() if k not in ('action','at')}
                self.emit('mapping_configuration',dict(s.telemetry_mapping,classification='DERIVED_COMPUTATION'))
            if action in ('teleport','translate','velocity','trajectory','stop','reset'): self.cancel_active()
            if action in ('teleport','translate'):
                s.position=vector(c['position'] if action=='teleport' else add(s.position,c['delta']))
                s.velocity=(0.,)*3; s.acceleration=(0.,)*3
                s.movement_mode='manual'; s.simulation_status='STOPPED'
            elif action=='velocity':
                s.velocity=c['velocity']; s.acceleration=c.get('acceleration',(0.,)*3)
                s.movement_mode='velocity'; s.simulation_status='RUNNING'
                self.active=identifier; ongoing=True
            elif action=='appearance':
                for key in ('radius','color','intensity','representation'):
                    if key in c: setattr(s,key,c[key])
            elif action=='collision':
                s.collision_mode=c['mode']; self.restitution=c['restitution']
                self.wall_x=c.get('wall_x',self.wall_x)
            elif action=='trajectory':
                self.path=Path(c['trajectory'],s.position); self.path_elapsed=0.
                s.acceleration=(0.,)*3
                s.movement_mode=c['trajectory']['kind']; s.simulation_status='RUNNING'
                self.active=identifier; ongoing=True
                self.emit('trajectory',{'command_id':identifier,'spec':c['trajectory'],'origin':s.position})
            elif action=='pause':
                if s.simulation_status!='PAUSED': self.resume_status=s.simulation_status
                s.simulation_status='PAUSED'; self.transition(self.active,'PAUSED')
            elif action=='resume':
                if s.simulation_status=='PAUSED': s.simulation_status=self.resume_status
                self.transition(self.active,'ACTIVE')
            elif action in ('stop','reset'):
                s.velocity=(0.,)*3; s.acceleration=(0.,)*3; s.simulation_status='STOPPED'; s.movement_mode='manual'
                if action=='reset':
                    s.position=self.initial
                    for _,pid,_ in self.pending: self.transition(pid,'CANCELLED','reset')
                    self.pending=[]
            elif action=='cancel':
                target=c['command_id']
                if target==self.active:
                    self.cancel_active(); s.simulation_status='STOPPED'; s.velocity=(0.,)*3
                else:
                    found=any(x[1]==target for x in self.pending)
                    if not found: raise ValueError('Command is not active or scheduled')
                    self.pending=[x for x in self.pending if x[1]!=target]
                    self.transition(target,'CANCELLED','operator')
            self.update_oscillator()
            s.state_version+=1; s.timestamp_ns=time.time_ns()
            self.emit('state_transition',s.snapshot())
            if not ongoing: self.transition(identifier,'COMPLETED')
        except (ValueError,ArithmeticError) as exc:
            self.transition(identifier,'FAILED',str(exc))

    def collide(self,old,new,velocity):
        s=self.state
        if s.collision_mode=='pass': return new,velocity,False
        # Infinite, zero-thickness plane. Sweep sphere center against expanded plane.
        side=-1 if old[0]<=self.wall_x else 1
        boundary=self.wall_x+side*s.radius
        penetration=(old[0]-self.wall_x)*side < s.radius-1e-12
        crossing=(new[0]-boundary)*side < -1e-12
        if not (penetration or crossing): return new,velocity,False
        fraction=0. if penetration or new[0]==old[0] else max(0.,min(1.,(boundary-old[0])/(new[0]-old[0])))
        contact=tuple(a+(b-a)*fraction for a,b in zip(old,new))
        contact=(boundary,contact[1],contact[2])
        mode=s.collision_mode
        if mode=='stop': result=contact; velocity=(0.,)*3; s.simulation_status='STOPPED'; s.acceleration=(0.,)*3
        elif mode=='slide':
            result=(boundary,new[1],new[2]); velocity=(0.,velocity[1],velocity[2]); s.acceleration=(0.,s.acceleration[1],s.acceleration[2])
        else:
            restitution=self.restitution if mode=='custom' else 1.
            result=(boundary+abs(new[0]-boundary)*side*restitution,new[1],new[2])
            velocity=(abs(velocity[0])*side*restitution,velocity[1],velocity[2])
        self.emit('interaction',{'mode':mode,'wall_x':self.wall_x,'contact':contact,'fraction':fraction,'restitution':self.restitution})
        return result,velocity,True

    def step(self):
        s=self.state
        if s.simulation_status=='PAUSED': return
        s.tick+=1; s.sim_time=s.tick/self.hz
        if s.entity_active and s.oscillator_enabled:
            s.oscillator_time+=self.dt; self.update_oscillator()
            s.state_version+=1; s.timestamp_ns=time.time_ns()
        # Motion occurs over the preceding interval; commands at this tick then take effect.
        if s.simulation_status=='RUNNING':
            try:
                done=False
                if self.path:
                    self.path_elapsed+=self.dt
                    duration=self.path.spec['duration']; t=min(self.path_elapsed,duration)
                    new=vector(self.path.position(t)); velocity=vector(self.path.velocity(t))
                    done=self.path_elapsed+1e-10>=duration
                else:
                    new=vector(tuple(p+v*self.dt+.5*a*self.dt*self.dt for p,v,a in zip(s.position,s.velocity,s.acceleration)))
                    velocity=vector(tuple(v+a*self.dt for v,a in zip(s.velocity,s.acceleration)))
                new,velocity,hit=self.collide(s.position,new,velocity)
                s.position=vector(new); s.velocity=vector(velocity)
                if hit:
                    self.transition(self.active,'COMPLETED','collision changed flow')
                    self.active=None; self.path=None; s.movement_mode='velocity'
                    self.emit('state_transition',s.snapshot())
                elif done:
                    next_behavior=self.path.spec['next']
                    self.transition(self.active,'COMPLETED')
                    self.active=None; self.path=None
                    s.movement_mode='velocity' if next_behavior=='continue' else 'manual'
                    if next_behavior=='stop': s.velocity=(0.,)*3; s.simulation_status='STOPPED'
                    self.emit('state_transition',s.snapshot())
                s.state_version+=1; s.timestamp_ns=time.time_ns()
            except (ValueError,ArithmeticError) as exc:
                self.transition(self.active,'FAILED',str(exc)); self.active=None; self.path=None
                s.simulation_status='STOPPED'; s.velocity=(0.,)*3
                self.emit('state_transition',s.snapshot())
        while self.pending and self.pending[0][0]<=s.sim_time+1e-12:
            _,identifier,c=self.pending.pop(0); self.execute(identifier,c)
