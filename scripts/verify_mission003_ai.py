import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point import Kernel
from atomverse_point.ai import propose
from owned_ollama import owned_ollama,api

parser=argparse.ArgumentParser();parser.add_argument('--ollama',required=True);parser.add_argument('--models',required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
report={'status':'FAIL','method':'real isolated Ollama server using existing weights','model_downloaded':False,'cases':[]}
with owned_ollama(args.ollama,args.models,root/'.local/mission003-ollama.log') as endpoint:
    report['details']=api(endpoint,'/api/show',{'model':'qwen3.8:27b'})['details']
    for prompt,expected in [
        ('Move the sphere to X 10, Y 5, Z 3.',{'action':'teleport','position':(10.,5.,3.)}),
        ('Move the sphere BY the displacement X 1, Y -2, Z 3.',{'action':'translate','delta':(1.,-2.,3.)}),
        ('Enable the oscillator at frequency 2, amplitude 3, phase 0.',{'action':'oscillator','enabled':True,'frequency':2.,'amplitude':3.,'phase':0.})]:
        result=propose(prompt,Kernel().state.snapshot(),endpoint,num_gpu=8,timeout=120)
        passed=all(result['command'].get(k)==v for k,v in expected.items())
        report['cases'].append({'pass':passed,'proposal':result})
        print('Real model case: '+str(passed),flush=True)
report['owned_server_stopped']=True
report['status']='PASS' if all(c['pass'] for c in report['cases']) else 'FAIL'
(root/'EVIDENCE/MISSION-003-AI.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert report['status']=='PASS'
