import json
import math
import sqlite3
import time
import pytest
from atomverse_point.kernel import Kernel
from atomverse_point.model import PointState,normalize_snapshot,validate_command
from atomverse_point.oscillator import signal,map_amplitude,invert_amplitude
from atomverse_point.history import History,exact_reexecution,replay

def steps(k,n):
    for _ in range(n): k.step()

def test_oscillator_formula_units_and_pause():
    k=Kernel(100); k.submit({'action':'oscillator','frequency':2,'amplitude':3,'phase':math.pi/2,'enabled':True})
    assert k.state.oscillator_value==pytest.approx(3)
    steps(k,25); assert k.state.oscillator_value==pytest.approx(-3)
    k.submit({'action':'pause'}); saved=k.state.snapshot(); steps(k,100)
    assert k.state.snapshot()==saved
    k.submit({'action':'resume'}); steps(k,25); assert k.state.oscillator_value==pytest.approx(3)

@pytest.mark.parametrize('c',[{'action':'oscillator','frequency':-1},{'action':'oscillator','amplitude':float('nan')},{'action':'oscillator','enabled':'yes'},{'action':'information','information_state':{'bad':float('inf')}},{'action':'mapping','input_min':100,'input_max':0}])
def test_invalid_entity_command_rejection(c):
    with pytest.raises(ValueError): validate_command(c)

def test_identity_delete_create_restore_and_history_semantics():
    k=Kernel(); k.submit({'action':'teleport','position':[1,2,-3]}); saved=k.state.snapshot()
    pid=k.submit({'action':'create'}); assert k.projections[pid]['status']=='FAILED'
    k.submit({'action':'delete'}); assert not k.state.entity_active
    pid=k.submit({'action':'teleport','position':[9,9,9]}); assert k.projections[pid]['status']=='FAILED'
    k.submit({'action':'create'}); assert k.state.point_id!=saved['point_id'] and k.state.entity_active
    steps(k,10); tick=k.state.tick
    k.submit({'action':'restore','state':saved})
    assert k.state.point_id==saved['point_id'] and k.state.position==saved['position'] and k.state.tick==tick
    assert k.state.simulation_status=='PAUSED' and not k.state.telemetry_mapping['enabled']

def test_schema1_snapshot_reads_without_rewrite():
    raw=PointState().snapshot()
    old_keys={'point_id','position','radius','color','velocity','acceleration','timestamp_ns','state_version','movement_mode','collision_mode','simulation_status','tick','sim_time','intensity','representation'}
    old={k:v for k,v in raw.items() if k in old_keys}; original=json.dumps(old)
    upgraded=normalize_snapshot(old)
    assert upgraded['entity_id']==old['point_id'] and upgraded['schema_version']==2
    assert not upgraded['oscillator_enabled'] and original==json.dumps(old)

def test_mapping_clamps_is_inspectable_and_inverse_is_partial():
    c=validate_command({'action':'mapping','enabled':True,'input_min':0,'input_max':100,'amplitude_min':1,'amplitude_max':3})
    mapped=map_amplitude(25,c); assert mapped['value']==1.5 and not mapped['clamped']
    assert invert_amplitude(1.5,c)==25
    assert map_amplitude(200,c)['value']==3 and map_amplitude(200,c)['clamped']
    with pytest.raises(ValueError): invert_amplitude(3,c)

def test_telemetry_cannot_contaminate_state_and_disable_restores_manual_amplitude():
    k=Kernel(100); k.submit({'action':'oscillator','enabled':True,'amplitude':5,'frequency':1})
    k.submit({'action':'mapping','enabled':True,'amplitude_min':0,'amplitude_max':2})
    with pytest.raises(ValueError): k.observe_telemetry({'classification':'CONTROLLED_TEST','values':{'cpu_utilization':float('nan')}})
    k.observe_telemetry({'classification':'CONTROLLED_TEST','values':{'cpu_utilization':25},'fresh':True})
    k.step(); assert k.state.effective_amplitude==.5 and k.state.amplitude==5
    k.submit({'action':'mapping','enabled':False}); assert k.state.effective_amplitude==5
    k.submit({'action':'mapping','enabled':True}); k.observe_telemetry({'classification':'CONTROLLED_TEST','values':{'cpu_utilization':25},'fresh':False}); k.step()
    assert k.state.effective_amplitude==5 and 'UNAVAILABLE' in k.state.telemetry_status

def test_exact_command_reexecution_matches_oscillator_and_position(tmp_path):
    k=Kernel(100); h=History(tmp_path/'history.db',k.state.point_id,{'sim_hz':100})
    commands={0:[{'action':'oscillator','enabled':True,'frequency':2,'amplitude':3},{'action':'velocity','velocity':[1,-2,3]}],20:[{'action':'oscillator','phase':.5}],50:[{'action':'teleport','position':[4,2,1]}]}
    for tick in range(100):
        for cmd in commands.get(tick,[]): k.submit(cmd)
        for e in k.drain_events(): h.record(e)
        k.step()
        for e in k.drain_events(): h.record(e)
        h.sample(k.state.snapshot())
    h.close(); outputs=exact_reexecution(h.path,h.session_id)
    assert len(outputs)==100
    for item in outputs:
        assert list(item['state']['position'])==item['recorded']['position']
        assert item['state']['oscillator_value']==item['recorded']['oscillator_value']
    assert len(replay(h.path,h.session_id))>=100

def test_full_schedule_does_not_block_direct_stop():
    k=Kernel()
    for i in range(1024): k.submit({'action':'teleport','position':[0,0,0],'at':100+i})
    k.submit({'action':'stop'})
    assert k.state.simulation_status=='STOPPED'
    with pytest.raises(ValueError): k.submit({'action':'teleport','position':[0,0,0],'at':9999})

@pytest.mark.parametrize('field,value',[('tick',float('nan')),('state_version',True),('timestamp_ns',-1),('sim_time',float('inf')),('oscillator_value',float('nan')),('entity_id','different'),('movement_mode','shell'),('entity_active',False)])
def test_corrupt_restore_rejected_before_any_state_mutation(field,value):
    k=Kernel(); before=k.state.snapshot(); corrupted=dict(before,**{field:value})
    with pytest.raises(ValueError): k.submit({'action':'restore','state':corrupted})
    assert k.state.snapshot()==before and not k.events
