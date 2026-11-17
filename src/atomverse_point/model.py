"""Validated public command boundary and double-precision point state."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import ast
import math
import time
import uuid
import json

LIMIT = 1e9

def number(value, low=-LIMIT, high=LIMIT):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Expected a finite number')
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Number must be finite and in [{low}, {high}]')
    return value

def vector(value, size=3, low=-LIMIT, high=LIMIT):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'Expected {size} coordinates')
    return tuple(number(x, low, high) for x in value)

FUNCTIONS = {'sin': math.sin, 'cos': math.cos, 'sqrt': math.sqrt, 'abs': abs}

class Expression:
    """Tiny AST interpreter: no eval, attribute access, imports or Python execution."""
    def __init__(self, source):
        if not isinstance(source, str) or len(source) > 256:
            raise ValueError('Expression must contain at most 256 characters')
        try:
            self.tree = ast.parse(source, mode='eval').body
        except (SyntaxError, RecursionError) as exc:
            raise ValueError('Invalid mathematical expression') from exc
        nodes = list(ast.walk(self.tree))
        allowed = (ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Call)
        if len(nodes) > 80 or any(not isinstance(n, allowed) for n in nodes):
            raise ValueError('Only bounded arithmetic, t, pi, sin, cos, sqrt and abs are allowed')
        for n in nodes:
            if isinstance(n, ast.Name) and n.id not in {'t', 'pi', *FUNCTIONS}:
                raise ValueError('Unknown expression name')
            if isinstance(n, ast.Constant):
                number(n.value, -1e6, 1e6)
            if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in FUNCTIONS or len(n.args) != 1 or n.keywords):
                raise ValueError('Only single-argument mathematical functions are allowed')
        self(0.0)

    def __call__(self, t):
        def calc(n, depth=0):
            if depth > 16:
                raise ValueError('Expression depth limit exceeded')
            if isinstance(n, ast.Constant):
                v = n.value
            elif isinstance(n, ast.Name):
                if n.id not in ('t', 'pi'):
                    raise ValueError('Function name requires parentheses')
                v = t if n.id == 't' else math.pi
            elif isinstance(n, ast.UnaryOp):
                v = calc(n.operand, depth+1) * (-1 if isinstance(n.op, ast.USub) else 1)
            elif isinstance(n, ast.Call):
                v = FUNCTIONS[n.func.id](calc(n.args[0], depth+1))
            else:
                a, b = calc(n.left, depth+1), calc(n.right, depth+1)
                if isinstance(n.op, ast.Add): v = a+b
                elif isinstance(n.op, ast.Sub): v = a-b
                elif isinstance(n.op, ast.Mult): v = a*b
                elif isinstance(n.op, ast.Div): v = a/b
                else:
                    if abs(b) > 8: raise ValueError('Exponent magnitude exceeds 8')
                    v = a**b
            return number(v, -1e12, 1e12)
        try:
            return calc(self.tree)
        except (ArithmeticError, TypeError) as exc:
            raise ValueError('Expression domain error') from exc

def trajectory(raw):
    if not isinstance(raw, dict): raise ValueError('Trajectory must be an object')
    allowed = {'kind','duration','target','amplitude','frequency','phase','pitch','growth','expressions','points','next'}
    if set(raw)-allowed: raise ValueError('Unknown trajectory field')
    kind = raw.get('kind')
    if kind not in ('line','circle','spiral','helix','custom','polyline'):
        raise ValueError('Unknown trajectory kind')
    d = dict(raw)
    d['duration'] = number(d.get('duration',10), .001, 86400)
    d['next'] = d.get('next','stop')
    if d['next'] not in ('stop','continue'): raise ValueError('Invalid next behavior')
    if kind == 'line': d['target'] = vector(d.get('target'))
    if kind in ('circle','spiral','helix'):
        for key,default,low,high in [('amplitude',2,0,1e6),('frequency',.2,-100,100),('phase',0,-1e6,1e6),('pitch',.4,-1e6,1e6),('growth',.1,-1e6,1e6)]:
            d[key] = number(d.get(key,default),low,high)
    if kind == 'custom':
        e = d.get('expressions')
        if not isinstance(e,list) or len(e)!=3: raise ValueError('Provide three expressions for displacement')
        for x in e: Expression(x)
    if kind == 'polyline':
        p = d.get('points')
        if not isinstance(p,list) or not 2<=len(p)<=4096: raise ValueError('Provide 2 to 4096 absolute positions')
        d['points'] = [vector(x) for x in p]
    # Reject inappropriate fields as well as unknown ones.
    specific = {'line':{'target'},'circle':{'amplitude','frequency','phase','pitch','growth'},'spiral':{'amplitude','frequency','phase','pitch','growth'},'helix':{'amplitude','frequency','phase','pitch','growth'},'custom':{'expressions'},'polyline':{'points'}}
    if set(d)-({'kind','duration','next'}|specific[kind]): raise ValueError('Field does not apply to trajectory kind')
    return d

ACTIONS = {
    'teleport': {'position'}, 'translate': {'delta'}, 'velocity': {'velocity','acceleration'},
    'appearance': {'radius','color','intensity','representation'}, 'collision': {'mode','restitution','wall_x'},
    'trajectory': {'trajectory'}, 'pause': set(), 'resume': set(), 'stop': set(), 'reset': set(),
    'cancel': {'command_id'},
    'create': {'entity_id'}, 'delete': set(), 'restore': {'state'},
    'oscillator': {'frequency','amplitude','phase','enabled'},
    'information': {'information_state'},
    'mapping': {'enabled','metric','input_min','input_max','amplitude_min','amplitude_max'},
}

METRICS = {'cpu_utilization','gpu_utilization','gpu_power_watts','cpu_clock_mhz','gpu_clock_mhz','memory_utilization'}

def information(value):
    if not isinstance(value,dict) or len(value)>32: raise ValueError('Information state must be an object with at most 32 fields')
    def check(obj,depth=0):
        if depth>4: raise ValueError('Information state nesting limit exceeded')
        if isinstance(obj,dict):
            if any(not isinstance(k,str) or len(k)>64 for k in obj): raise ValueError('Invalid information key')
            for v in obj.values(): check(v,depth+1)
        elif isinstance(obj,list):
            if len(obj)>128: raise ValueError('Information list limit exceeded')
            for v in obj: check(v,depth+1)
        elif isinstance(obj,str):
            if len(obj)>1024: raise ValueError('Information string limit exceeded')
        elif obj is not None and not isinstance(obj,bool): number(obj)
    check(value)
    encoded=json.dumps(value,allow_nan=False)
    if len(encoded)>16384: raise ValueError('Information state exceeds 16 KiB')
    return json.loads(encoded)

def mapping(raw):
    if not isinstance(raw,dict): raise ValueError('Mapping must be an object')
    if 'enabled' in raw and not isinstance(raw['enabled'],bool): raise ValueError('Mapping enabled must be boolean')
    d={'enabled':raw.get('enabled',False),'metric':raw.get('metric','cpu_utilization'),
       'input_min':number(raw.get('input_min',0)), 'input_max':number(raw.get('input_max',100)),
       'amplitude_min':number(raw.get('amplitude_min',0),0,1e6),'amplitude_max':number(raw.get('amplitude_max',1),0,1e6)}
    if d['metric'] not in METRICS or d['input_min']>=d['input_max']: raise ValueError('Invalid telemetry mapping range or metric')
    return d

def normalize_snapshot(raw):
    """Read schema 1 records without rewriting their historical bytes."""
    if not isinstance(raw,dict) or isinstance(raw.get('schema_version',1),bool) or raw.get('schema_version',1) not in (1,2): raise ValueError('Unsupported state schema')
    defaults=PointState().snapshot()
    if set(raw)-set(defaults)-{'event_seq','restored_from'}: raise ValueError('Unknown state field')
    if 'point_id' not in raw or not isinstance(raw['point_id'],str) or len(raw['point_id'])>64: raise ValueError('Missing point identity')
    d=dict(defaults,**raw); d['entity_id']=d['point_id']; d['schema_version']=2
    if raw.get('entity_id',raw['point_id'])!=raw['point_id']: raise ValueError('Entity identity aliases disagree')
    for key in ('tick','state_version','timestamp_ns'):
        if isinstance(d[key],bool) or not isinstance(d[key],int) or not 0<=d[key]<2**63: raise ValueError('Invalid integer state field: '+key)
    d['sim_time']=number(d['sim_time'],0,1e9)
    d['oscillator_value']=number(d['oscillator_value'],-1e6,1e6)
    d['effective_amplitude']=number(d['effective_amplitude'],0,1e6)
    if d['movement_mode'] not in ('manual','velocity','line','circle','spiral','helix','custom','polyline'): raise ValueError('Invalid movement mode')
    if d['simulation_status'] not in ('RUNNING','PAUSED','STOPPED','DELETED','FAULT'): raise ValueError('Invalid execution status')
    for key in ('position','velocity','acceleration'): d[key]=vector(d[key])
    d['color']=vector(d['color'],4,0,1); d['radius']=number(d['radius'],.001,1e6)
    for key,low,high in [('frequency',0,1000),('amplitude',0,1e6),('phase',-1e6,1e6),('oscillator_time',0,1e9),('intensity',0,5)]: d[key]=number(d[key],low,high)
    if not isinstance(d['entity_active'],bool) or not isinstance(d['oscillator_enabled'],bool): raise ValueError('Invalid state flags')
    if d['representation'] not in ('solid','wireframe','transparent','luminous','center'): raise ValueError('Invalid representation')
    if d['collision_mode'] not in ('pass','stop','reflect','slide','custom'): raise ValueError('Invalid collision mode')
    d['information_state']=information(d['information_state']); d['telemetry_mapping']=mapping(d['telemetry_mapping'])
    return d

def validate_command(raw):
    if not isinstance(raw,dict) or raw.get('action') not in ACTIONS: raise ValueError('Unknown command action')
    action = raw['action']
    if set(raw)-({'action','at'}|ACTIONS[action]): raise ValueError('Unknown command field')
    c = dict(raw)
    if 'at' in c: c['at'] = number(c['at'],0,1e9)
    for key in ('position','delta','velocity','acceleration'):
        if key in c: c[key] = vector(c[key])
    required = {'teleport':'position','translate':'delta','velocity':'velocity','trajectory':'trajectory','collision':'mode','cancel':'command_id'}
    if action in required and required[action] not in c: raise ValueError('Missing '+required[action])
    if action=='appearance':
        if not (set(c)&ACTIONS[action]): raise ValueError('No appearance change supplied')
        if 'radius' in c: c['radius'] = number(c['radius'],.001,1e6)
        if 'color' in c: c['color'] = vector(c['color'],4,0,1)
        if 'intensity' in c: c['intensity'] = number(c['intensity'],0,5)
        if 'representation' in c and c['representation'] not in ('solid','wireframe','transparent','luminous','center'): raise ValueError('Unknown representation')
    if action=='collision':
        if c['mode'] not in ('pass','stop','reflect','slide','custom'): raise ValueError('Unknown collision mode')
        c['restitution'] = number(c.get('restitution',1),0,1)
        if 'wall_x' in c: c['wall_x']=number(c['wall_x'],-1e6,1e6)
    if action=='trajectory': c['trajectory']=trajectory(c['trajectory'])
    if action=='cancel':
        try: uuid.UUID(c['command_id'])
        except (ValueError, TypeError, AttributeError) as exc: raise ValueError('Invalid command ID') from exc
    if action=='oscillator':
        if not (set(c)&ACTIONS[action]): raise ValueError('No oscillator parameters supplied')
        for key,low,high in [('frequency',0,1000),('amplitude',0,1e6),('phase',-1e6,1e6)]:
            if key in c: c[key]=number(c[key],low,high)
        if 'enabled' in c and not isinstance(c['enabled'],bool): raise ValueError('Oscillator enabled must be boolean')
    if action=='information': c['information_state']=information(c.get('information_state'))
    if action=='mapping': c=dict(mapping(c),action=action,**({'at':c['at']} if 'at' in c else {}))
    if action=='restore':
        c['state']=normalize_snapshot(c.get('state'))
        if not c['state']['entity_active']: raise ValueError('Choose an active historical state to restore')
    if action=='create' and 'entity_id' in c:
        try: uuid.UUID(c['entity_id'])
        except (ValueError,TypeError,AttributeError) as exc: raise ValueError('Invalid entity UUID') from exc
    return c

@dataclass
class PointState:
    point_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position: tuple = (0.,0.,0.)
    radius: float = .5
    color: tuple = (.15,.65,1.,1.)
    velocity: tuple = (0.,0.,0.)
    acceleration: tuple = (0.,0.,0.)
    timestamp_ns: int = field(default_factory=time.time_ns)
    state_version: int = 0
    movement_mode: str = 'manual'
    collision_mode: str = 'pass'
    simulation_status: str = 'STOPPED'
    tick: int = 0
    sim_time: float = 0.
    intensity: float = 1.
    representation: str = 'solid'
    entity_active: bool = True
    frequency: float = 1.
    amplitude: float = 1.
    phase: float = 0.
    oscillator_enabled: bool = False
    oscillator_time: float = 0.
    oscillator_value: float = 0.
    effective_amplitude: float = 1.
    information_state: dict = field(default_factory=dict)
    telemetry_mapping: dict = field(default_factory=lambda:mapping({}))
    telemetry_status: str = 'DISABLED'

    def snapshot(self):
        return dict(asdict(self),schema_version=2,entity_id=self.point_id)
