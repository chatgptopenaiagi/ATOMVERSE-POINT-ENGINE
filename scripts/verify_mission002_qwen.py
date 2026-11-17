import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point.ai import propose
from atomverse_point.model import PointState
from owned_ollama import owned_ollama,api

def main():
    p=argparse.ArgumentParser(); p.add_argument('--ollama',required=True); p.add_argument('--models',required=True); p.add_argument('--executable',required=True); p.add_argument('--gui-only',action='store_true'); p.add_argument('--skip-gui',action='store_true'); p.add_argument('--gpu-layers',type=int,default=0); args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; report={'status':'PARTIAL','model':'qwen3.8:27b','model_downloaded':False,'cases':[]}
    if args.gui_only and (root/'EVIDENCE/MISSION-002-QWEN-VERIFICATION.json').is_file(): report=json.loads((root/'EVIDENCE/MISSION-002-QWEN-VERIFICATION.json').read_text())
    state=PointState(position=(-2.,1.,-3.)).snapshot()
    cases=[
        ('absolute','Move the sphere to X 10, Y 5, Z 3.',lambda c:c=={'action':'teleport','position':(10.,5.,3.)}),
        ('relative','Move the sphere BY the displacement X 1, Y -2, Z 3.',lambda c:c=={'action':'translate','delta':(1.,-2.,3.)}),
        ('radius','Set the radius to 2.',lambda c:c.get('action')=='appearance' and c.get('radius')==2),
        ('color','Set the sphere color to opaque blue, RGBA 0,0,1,1.',lambda c:c.get('action')=='appearance' and c.get('color')==(0.,0.,1.,1.)),
        ('oscillator','Enable the oscillator at frequency 2, amplitude 3, phase 0.',lambda c:c.get('action')=='oscillator' and c.get('frequency')==2 and c.get('amplitude')==3 and c.get('phase')==0 and c.get('enabled') is True),
        ('collision','Set wall collision mode to reflect.',lambda c:c.get('action')=='collision' and c.get('mode')=='reflect'),
        ('trajectory','Follow a helical trajectory for 2 simulation seconds.',lambda c:c.get('action')=='trajectory' and c.get('trajectory',{}).get('kind')=='helix' and c['trajectory']['duration']==2),
        ('history','Query the most recent 5 historical events.',lambda c:c=={'action':'history_query','limit':5}),
        ('explanation','Explain in one short sentence whether oscillator amplitude is physical energy. Cite current_state.',lambda c:c.get('action')=='explain' and 'current_state' in c.get('evidence_refs',[]) and len(c.get('explanation',''))>10),
    ]
    try:
        with owned_ollama(args.ollama,args.models,root/'.local/mission002-ollama.log') as endpoint:
            show=api(endpoint,'/api/show',{'model':report['model']}); report['actual_details']=show.get('details')
            for name,text,expected in ([] if args.gui_only else cases):
                print('Testing Qwen '+name,flush=True)
                started=time.perf_counter()
                try:
                    result=propose(text,state,endpoint,num_gpu=args.gpu_layers,timeout=150)
                    report['cases'].append({'name':name,'pass':bool(expected(result['command'])),'result':result})
                except Exception as exc: report['cases'].append({'name':name,'pass':False,'error':str(exc),'seconds':time.perf_counter()-started})
                (root/'.local/mission002-qwen-progress.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            report['loaded_configuration']=api(endpoint,'/api/ps')
            report['gpu_layers_requested']=args.gpu_layers
            if not args.skip_gui:
                target=root/'.local/mission002-packaged-gui-ai'
                command=[args.executable,'--data-dir',str(root/'.local/mission002-packaged-ai-data'),'--verify-ui',str(target),'--verify-ai','--ai-endpoint',endpoint,'--ai-gpu',str(args.gpu_layers)]
                result=subprocess.run(command,timeout=150)
                report['packaged_gui_exit_code']=result.returncode
                gui=json.loads((target/'gui-verification.json').read_text(encoding='utf-8'))
                (root/'EVIDENCE/MISSION-002-GUI-VERIFICATION.json').write_text(json.dumps(gui,indent=2),encoding='utf-8')
                report['packaged_ai_pass']=gui['status']=='PASS' and result.returncode==0
                report['executable_sha256']=hashlib.sha256(Path(args.executable).read_bytes()).hexdigest()
            report['status']='PASS' if all(c['pass'] for c in report['cases']) and (args.skip_gui or report['packaged_ai_pass']) else 'PARTIAL'
    except Exception as exc: report['error']=str(exc)
    report['owned_server_stopped']=True
    (root/'EVIDENCE/MISSION-002-QWEN-VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Mission 002 Qwen verification: '+report['status'],flush=True)
if __name__=='__main__': main()
