"""Test-only isolated Ollama process. Never modifies global server settings."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import psutil

def api(endpoint,route,payload=None,timeout=10):
    request=urllib.request.Request(endpoint+route,json.dumps(payload).encode() if payload else None,{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as response: return json.load(response)

@contextmanager
def owned_ollama(executable,models,log_path,port=11439):
    with socket.socket() as sock: sock.bind(('127.0.0.1',port))
    endpoint=f'http://127.0.0.1:{port}'
    env=dict(os.environ,OLLAMA_HOST=f'127.0.0.1:{port}',OLLAMA_MODELS=str(models),OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1')
    with Path(log_path).open('w') as log:
        process=subprocess.Popen([str(executable),'serve'],env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try: api(endpoint,'/api/tags'); break
            except OSError: time.sleep(.2)
        else: raise RuntimeError('Owned local inference server did not start')
        yield endpoint
    finally:
        try: children=psutil.Process(process.pid).children(recursive=True)
        except psutil.Error: children=[]
        for child in children:
            try: child.terminate()
            except psutil.Error: pass
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        _,alive=psutil.wait_procs(children,timeout=5)
        for child in alive:
            try: child.kill()
            except psutil.Error: pass
