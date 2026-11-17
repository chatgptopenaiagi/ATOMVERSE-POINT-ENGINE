"""Deterministic vectors shared by installed desktop, wheel and Android checks.

These are computational outputs, not hardware measurements. External acceptance
compares floats with absolute/relative tolerance 1e-10, excluding wall clocks/IDs.
"""
from .kernel import Kernel


def vectors():
    results = {}
    scenarios = {
        'absolute_relative': ([{'action':'teleport','position':[-2,3,-4]}, {'action':'translate','delta':[1,-2,3]}], 0),
        'accelerated': ([{'action':'velocity','velocity':[1,-2,3],'acceleration':[.5,0,-.25]}], 240),
        'line': ([{'action':'trajectory','trajectory':{'kind':'line','target':[3,-2,1],'duration':1}}], 240),
        'circle': ([{'action':'trajectory','trajectory':{'kind':'circle','amplitude':2,'frequency':.5,'duration':2}}], 60),
        'helix': ([{'action':'trajectory','trajectory':{'kind':'helix','amplitude':2,'frequency':.5,'pitch':.4,'duration':2}}], 180),
        'spiral': ([{'action':'trajectory','trajectory':{'kind':'spiral','amplitude':2,'growth':.1,'frequency':.5,'duration':2}}], 180),
        'oscillator': ([{'action':'oscillator','enabled':True,'frequency':2,'amplitude':3,'phase':.25}], 73),
        'reflection': ([{'action':'collision','mode':'reflect'}, {'action':'velocity','velocity':[10,1,0]}], 240),
    }
    keys = ('position','velocity','radius','color','frequency','amplitude','phase','oscillator_value','oscillator_time','sim_time','tick','schema_version')
    for name, (commands, steps) in scenarios.items():
        k = Kernel(240)
        for command in commands: k.submit(command)
        for _ in range(steps): k.step()
        state = k.state.snapshot()
        results[name] = {key:state[key] for key in keys}
    return results
