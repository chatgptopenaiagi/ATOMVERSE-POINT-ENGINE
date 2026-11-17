import math
import pytest
from atomverse_point.kernel import Kernel,Path
from atomverse_point.model import Expression,validate_command,trajectory

def run(k,seconds):
    for _ in range(round(seconds*k.hz)): k.step()
    return k.state

def test_identity_center_signed_absolute_relative():
    k=Kernel(); identity=k.state.point_id
    k.submit({'action':'teleport','position':[-10,5,-3]})
    k.submit({'action':'translate','delta':[1,-2,5]})
    assert k.state.position==(-9,3,2) and k.state.point_id==identity

@pytest.mark.parametrize('radius',[0,-1,float('inf'),float('nan'),True,1e9])
def test_invalid_radius_rejected_without_mutation(radius):
    k=Kernel(); before=k.state.snapshot()
    with pytest.raises(ValueError): k.submit({'action':'appearance','radius':radius})
    assert k.state.snapshot()==before and not k.events

def test_rgba_and_geometry_independent_of_motion():
    k=Kernel(); k.submit({'action':'velocity','velocity':[1,-2,3]})
    k.submit({'action':'appearance','radius':2,'color':[1,.2,.3,.4],'intensity':2,'representation':'wireframe'})
    assert k.state.velocity==(1,-2,3) and k.state.color==(1,.2,.3,.4) and k.state.radius==2
    assert run(k,1).position==pytest.approx((1,-2,3),abs=1e-12)

def test_constant_acceleration():
    k=Kernel(100); k.submit({'action':'velocity','velocity':[1,2,-3],'acceleration':[2,-1,.5]})
    s=run(k,2); assert s.position==pytest.approx((6,2,-5),abs=1e-12)
    assert s.velocity==pytest.approx((5,0,-2))

def test_line_midpoint_and_completion():
    k=Kernel(100); pid=k.submit({'action':'trajectory','trajectory':{'kind':'line','duration':2,'target':[4,-2,6]}})
    assert run(k,1).position==pytest.approx((2,-1,3))
    assert run(k,1).position==pytest.approx((4,-2,6))
    assert k.projections[pid]['status']=='COMPLETED' and k.state.simulation_status=='STOPPED'

@pytest.mark.parametrize('kind',['circle','spiral','helix'])
def test_analytic_trajectories(kind):
    k=Kernel(200)
    k.submit({'action':'trajectory','trajectory':{'kind':kind,'duration':2,'amplitude':3,'frequency':.5,'phase':0,'pitch':2,'growth':1}})
    s=run(k,.5); r=3.5 if kind=='spiral' else 3
    assert s.position==pytest.approx((-3,r,1 if kind=='helix' else 0),abs=1e-11)

def test_pause_resume_preserves_local_path_time():
    k=Kernel(100); k.submit({'action':'trajectory','trajectory':{'kind':'helix','duration':10}})
    run(k,1); k.submit({'action':'pause'}); before=k.state.snapshot()
    run(k,2); assert k.state.snapshot()==before
    k.submit({'action':'resume'}); run(k,1); assert k.state.sim_time==2

def test_schedule_tick_boundary_and_cancel():
    k=Kernel(100); pid=k.submit({'action':'velocity','velocity':[1,0,0],'at':1})
    assert k.projections[pid]['status']=='SCHEDULED'
    assert run(k,1).position==(0,0,0)
    assert k.projections[pid]['status']=='ACTIVE'
    assert run(k,1).position==pytest.approx((1,0,0))
    k.submit({'action':'cancel','command_id':pid}); assert k.projections[pid]['status']=='CANCELLED'

@pytest.mark.parametrize('mode,expected,vx',[('pass',10,10),('stop',4.5,0),('reflect',-1,-10),('slide',4.5,0),('custom',1.75,-5)])
def test_swept_wall_prevents_tunneling(mode,expected,vx):
    k=Kernel(1); k.submit({'action':'collision','mode':mode,'restitution':.5})
    k.submit({'action':'velocity','velocity':[10,2,0]}); k.step()
    assert k.state.position[0]==pytest.approx(expected)
    assert k.state.velocity[0]==vx
    if mode=='stop': assert k.state.position[1]==pytest.approx(.9)
    elif mode=='slide': assert k.state.position[1]==2

def test_wall_from_positive_side_and_depenetration():
    k=Kernel(10); k.submit({'action':'teleport','position':[10,0,0]})
    k.submit({'action':'collision','mode':'stop'}); k.submit({'action':'velocity','velocity':[-100,0,0]}); k.step()
    assert k.state.position[0]==5.5
    k.submit({'action':'teleport','position':[5,0,0]}); k.submit({'action':'velocity','velocity':[1,0,0]}); k.step()
    assert k.state.position[0]==4.5

def test_custom_curve_and_polyline():
    k=Kernel(100); k.submit({'action':'trajectory','trajectory':{'kind':'custom','duration':2,'expressions':['t','t*t','sin(t)']}})
    assert run(k,1).position==pytest.approx((1,1,math.sin(1)))
    k.submit({'action':'reset'})
    k.submit({'action':'trajectory','trajectory':{'kind':'polyline','duration':2,'points':[[2,0,0],[2,2,0]]}})
    assert run(k,1).position==pytest.approx((2,0,0))
    assert run(k,1).position==pytest.approx((2,2,0))

@pytest.mark.parametrize('expr',["__import__('os')","t.__class__","[t for t in [1]]","sin(t,t)","2**100000000","True","open('a')","1/0"])
def test_untrusted_expressions_rejected(expr):
    with pytest.raises(ValueError): Expression(expr)

def test_runtime_domain_error_fails_projection_without_corrupting_position():
    k=Kernel(10); pid=k.submit({'action':'trajectory','trajectory':{'kind':'custom','duration':2,'expressions':['sqrt(1-t)','0','0']}})
    run(k,2)
    assert k.projections[pid]['status']=='FAILED'
    assert all(math.isfinite(v) for v in k.state.position) and k.state.simulation_status=='STOPPED'

@pytest.mark.parametrize('command',[{'action':'shell','command':'whoami'},{'action':'teleport','position':[0,1,float('nan')]},{'action':'stop','unknown':1},{'action':'appearance','color':[2,0,0,1]},{'action':'collision','mode':'physics'},{'action':'velocity','velocity':[True,0,0]}])
def test_strict_ai_boundary(command):
    with pytest.raises(ValueError): validate_command(command)

def test_deterministic_reexecution():
    def experiment():
        k=Kernel(240,point_id='test-point')
        k.submit({'action':'trajectory','trajectory':{'kind':'helix','duration':3,'amplitude':2,'frequency':.75,'pitch':.3}})
        states=[]
        for _ in range(720): k.step(); states.append((k.state.tick,k.state.position,k.state.velocity))
        return states
    assert experiment()==experiment()

def test_high_coordinate_precision():
    k=Kernel(); k.submit({'action':'teleport','position':[1e6,-1e6,1e6]})
    k.submit({'action':'translate','delta':[.000001,-.000001,.000001]})
    assert k.state.position==pytest.approx((1000000.000001,-1000000.000001,1000000.000001),abs=1e-10,rel=0)

def test_reset_cancels_schedule_without_resetting_clock_or_identity():
    k=Kernel(); identity=k.state.point_id
    pid=k.submit({'action':'teleport','position':[10,0,0],'at':10}); run(k,1)
    k.submit({'action':'reset'})
    assert k.projections[pid]['status']=='CANCELLED' and not k.pending
    assert k.state.sim_time==1 and k.state.point_id==identity

def test_projection_continue_velocity():
    k=Kernel(100); k.submit({'action':'trajectory','trajectory':{'kind':'line','duration':1,'target':[2,0,0],'next':'continue'}})
    assert run(k,2).position==pytest.approx((4,0,0),abs=1e-8)

def test_resume_after_collision_and_completed_continuation():
    k=Kernel(100); k.submit({'action':'trajectory','trajectory':{'kind':'line','duration':1,'target':[2,0,0],'next':'continue'}})
    run(k,1); k.submit({'action':'pause'}); k.submit({'action':'resume'})
    assert run(k,1).position==pytest.approx((4,0,0),abs=1e-8)

def test_failed_relative_command_does_not_cancel_existing_motion():
    k=Kernel(); k.submit({'action':'teleport','position':[1e9,0,0]})
    active=k.submit({'action':'velocity','velocity':[-1,0,0]})
    failed=k.submit({'action':'translate','delta':[1e9,0,0]})
    assert k.projections[failed]['status']=='FAILED' and k.active==active
    assert k.projections[active]['status']=='ACTIVE'
