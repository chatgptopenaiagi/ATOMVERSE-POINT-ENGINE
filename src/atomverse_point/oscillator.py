"""Dimensionless oscillator and inspectable affine telemetry mapping."""
import math
from .model import number

def signal(amplitude,frequency,phase,simulation_time):
    return amplitude*math.sin(2*math.pi*frequency*simulation_time+phase)

def map_amplitude(value,config):
    value=number(value)
    lo,hi=config['input_min'],config['input_max']
    normalized=(value-lo)/(hi-lo); bounded=min(1.,max(0.,normalized))
    out=config['amplitude_min']+bounded*(config['amplitude_max']-config['amplitude_min'])
    return {'value':out,'normalized':bounded,'clamped':normalized!=bounded,'classification':'DERIVED_COMPUTATION'}

def invert_amplitude(value,config):
    lo,hi=config['amplitude_min'],config['amplitude_max']
    if lo==hi: raise ValueError('Constant mapping is not invertible')
    fraction=(number(value)-lo)/(hi-lo)
    if not 0<fraction<1: raise ValueError('Clamped endpoints have no unique inverse')
    return config['input_min']+fraction*(config['input_max']-config['input_min'])
