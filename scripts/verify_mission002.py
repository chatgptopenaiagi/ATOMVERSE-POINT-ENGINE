"""Bounded real runtime, old-history compatibility and packaged headless checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point.kernel import Kernel
from atomverse_point.history import History,replay,sessions,exact_reexecution
from atomverse_point.runtime import Runtime

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--executable',required=True); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]; report={'method':'actual worker and packaged process; no simulated performance results','rates':[]}
    for hz in (240,1000,2000):
        path=root/'.local'/('mission002-rate-'+str(hz)+'-'+uuid.uuid4().hex[:8]+'.db')
        kernel=Kernel(hz); h=History(path,kernel.state.point_id,{'sim_hz':hz}); runtime=Runtime(kernel,h,hz)
        proc=psutil.Process(); rss=proc.memory_info().rss; start=time.perf_counter(); runtime.start()
        runtime.submit({'action':'oscillator','enabled':True,'frequency':2,'amplitude':3})
        runtime.submit({'action':'trajectory','trajectory':{'kind':'helix','duration':10}})
        for i in range(30):
            runtime.submit({'action':'appearance','intensity':1+i/100}); time.sleep(.1)
        runtime.close(); elapsed=time.perf_counter()-start; h.close()
        report['rates'].append({'requested_hz':hz,'seconds':elapsed,'actual_ticks_per_second':runtime.read()['tick']/elapsed,
                                'samples':h.samples_written,'dropped':h.dropped,'runtime':runtime.stats(),'local_journal':h.stats(),'rss_growth_bytes':proc.memory_info().rss-rss})
    old=root/'.local/mission002-baseline-data/history.db'
    if old.is_file():
        before_hash=hashlib.sha256(old.read_bytes()).hexdigest()
        old_session=sessions(old)[0][0]; values=replay(old,old_session)
        report['actual_mission001_history_compatibility']={'states_read':len(values),'schema2_defaults_supplied':all(s['schema_version']==2 and not s['oscillator_enabled'] for s in values),'original_file_unchanged_in_content':hashlib.sha256(old.read_bytes()).hexdigest()==before_hash}
    commands=root/'.local/headless-commands.json'; commands.write_text(json.dumps([{'action':'velocity','velocity':[1,2,3]},{'action':'oscillator','enabled':True,'amplitude':2,'frequency':1}]))
    output=root/'.local/mission002-headless.json'; data=root/'.local'/('headless-'+uuid.uuid4().hex[:8])
    run=subprocess.run([args.executable,'--headless','--seconds','2','--no-sql','--data-dir',str(data),'--command-file',str(commands),'--snapshot-out',str(output)],timeout=15)
    headless=json.loads(output.read_text()); assert run.returncode==0 and headless['status']=='PASS' and not headless['renderer_created']
    assert headless['state']['position'][0]>1.5 and headless['state']['oscillator_time']>1.5
    report['packaged_headless']={k:headless[k] for k in ('version','headless','renderer_created','status','runtime')}
    report['packaged_headless']['tick']=headless['state']['tick']; report['packaged_headless']['position']=headless['state']['position']
    report['executable_sha256']=hashlib.sha256(Path(args.executable).read_bytes()).hexdigest()
    report['sql_persistence']='See SQL-RECOVERY and SQL-THROUGHPUT; permanent database not provisioned. Temporary throughput is not permanent-storage throughput.'
    report['status']='PASS'; (root/'EVIDENCE/MISSION-002-PERFORMANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
