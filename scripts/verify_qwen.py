"""Bounded, private loopback verification of an existing model; no downloads."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point.ai import propose
from atomverse_point.model import PointState

def main():
    p=argparse.ArgumentParser(); p.add_argument('--ollama',required=True); p.add_argument('--models',required=True); p.add_argument('--output',default='QWEN-INFERENCE.json'); a=p.parse_args()
    root=Path(__file__).resolve().parents[1]; report={'status':'UNAVAILABLE','model_downloaded':False,'runs':[]}; server=None
    endpoint='http://127.0.0.1:11439'
    def api(route,payload=None,timeout=10):
        req=urllib.request.Request(endpoint+route,json.dumps(payload).encode() if payload else None,{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
    try:
        model='qwen3.8:27b'
        manifest=json.loads((Path(a.models)/'manifests/registry.ollama.ai/library/qwen3.8/27b').read_text())
        blobs=[Path(a.models)/'blobs'/x['digest'].replace(':','-') for x in manifest['layers']]
        report['all_blobs_present']=all(x.is_file() for x in blobs)
        report['total_blob_bytes']=sum(x.stat().st_size for x in blobs)
        assert report['all_blobs_present']
        with socket.socket() as sock: sock.bind(('127.0.0.1',11439))
        env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11439',OLLAMA_MODELS=a.models,OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1')
        with (root/'.local/ollama.log').open('w') as log:
            server=subprocess.Popen([a.ollama,'serve'],stdout=log,stderr=log,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(50):
            try: api('/api/tags'); break
            except OSError: time.sleep(.2)
        show=api('/api/show',{'model':model})
        report.update(model=model,details=show.get('details'),architecture_metadata={k:v for k,v in show.get('model_info',{}).items() if any(t in k for t in ('architecture','parameter_count','context_length','block_count','embedding_length','file_type'))})
        for gpu in (0,8):
            for repeat in range(2):
                print('Starting Qwen inference num_gpu='+str(gpu)+' repeat='+str(repeat),flush=True)
                start=time.perf_counter()
                try:
                    state=PointState(position=(-2.,1.,-3.)).snapshot()
                    r=propose('Move the sphere to X 10, Y 5, Z 3.',state,endpoint,model,gpu,timeout=150)
                    r.update(num_gpu_requested=gpu,repeat=repeat)
                    r['validated_expected_command']=r['command']=={'action':'teleport','position':(10.,5.,3.)}
                    r['tokens_per_second']=r['eval_count']/max(1,r['eval_duration_ns'])*1e9 if r['eval_count'] else None
                    r['loaded_models']=api('/api/ps').get('models')
                    report['runs'].append(r)
                    print('Inference complete in '+str(round(r['elapsed_seconds'],2))+' seconds',flush=True)
                except Exception as exc:
                    report['runs'].append({'num_gpu_requested':gpu,'repeat':repeat,'error':type(exc).__name__,'elapsed_seconds':time.perf_counter()-start})
                    break
            api('/api/generate',{'model':model,'keep_alive':0},timeout=20)
        valid=[r for r in report['runs'] if r.get('validated_expected_command')]
        report['status']='PASS' if valid else 'PARTIAL'
        report['inference_verified']=any('command' in r for r in report['runs'])
        report['expected_30b_found']=False
        report['limitation']='Existing model is qwen3.8:27b, not the requested 30B. Measured short-command results do not establish general planning accuracy.'
        if valid:
            best=min(valid,key=lambda r:r['elapsed_seconds'])
            report['fastest_measured_num_gpu']=best['num_gpu_requested']
    except Exception as exc: report['error']=str(exc)
    finally:
        if server:
            try: children=psutil.Process(server.pid).children(recursive=True)
            except psutil.Error: children=[]
            for proc in children:
                try: proc.terminate()
                except psutil.Error: pass
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
            _,alive=psutil.wait_procs(children,timeout=5)
            for proc in alive:
                try: proc.kill()
                except psutil.Error: pass
            report['owned_server_stopped']=server.poll() is not None
        # API /ps includes model names and digests, never private local paths.
        (root/'EVIDENCE'/a.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Qwen verification: '+report['status'],flush=True)
if __name__=='__main__': main()
