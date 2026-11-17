"""Verify an actual Windows candidate from a fresh directory outside the repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import time

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--executable',required=True); parser.add_argument('--label',required=True); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]; original=Path(args.executable).resolve(); work=Path(tempfile.mkdtemp(prefix='atomverse-windows-'))
    if (original.parent/'_internal').is_dir():
        shutil.copytree(original.parent,work/'application'); exe=work/'application'/original.name
    else:
        exe=work/original.name; shutil.copy2(original,exe)
    env=dict(os.environ); env.pop('PYTHONPATH',None); env.pop('PYTHONHOME',None)
    env['PATH']=os.path.join(os.environ['SystemRoot'],'System32')+os.pathsep+os.environ['SystemRoot']
    start=time.perf_counter()
    gui=subprocess.run([str(exe),'--no-sql','--data-dir',str(work/'gui-data'),'--verify-ui',str(work/'gui-evidence'),'--verify-ai-unavailable','--ai-endpoint','http://127.0.0.1:1'],cwd=work,env=env,timeout=150)
    elapsed=time.perf_counter()-start
    result=json.loads((work/'gui-evidence/gui-verification.json').read_text())
    assert gui.returncode==0 and result['status']=='PASS' and result['clean_shutdown'],result
    commands=work/'commands.json'; commands.write_text('[{"action":"teleport","position":[-3,2,1]},{"action":"oscillator","enabled":true,"frequency":2,"amplitude":3}]')
    headless=subprocess.run([str(exe),'--headless','--no-sql','--seconds','.5','--data-dir',str(work/'headless'),'--command-file',str(commands)],cwd=work,env=env,timeout=45)
    head=json.loads((work/'headless/headless-result.json').read_text())
    assert headless.returncode==0 and head['status']=='PASS' and head['state']['position']==[-3,2,1] and not head['renderer_created']
    conformance=subprocess.run([str(exe),'--conformance-out',str(work/'vectors.json')],cwd=work,env=env,timeout=45)
    assert conformance.returncode==0
    with sqlite3.connect(work/'gui-data/history.db') as c: integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    assert integrity=='ok'
    data=exe.read_bytes(); machine=struct.unpack_from('<H',data,struct.unpack_from('<I',data,0x3c)[0]+4)[0]; assert machine==0x8664
    report={'status':'PASS','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'architecture':'Windows x64','outside_source_directory':True,
            'python_removed_from_PATH':True,'bundled_python':True,'gui':result,'gui_test_seconds_including_startup':elapsed,
            'headless':'PASS','sqlite_integrity':integrity,'vectors':json.loads((work/'vectors.json').read_text()),
            'test_method':'actual copied executable, native GUI controls, framebuffer capture, SQLite and subprocess exit checks'}
    (root/f'EVIDENCE/MISSION-003-WINDOWS-{args.label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    shutil.copy2(work/'gui-evidence/application.png',root/f'EVIDENCE/MISSION-003-WINDOWS-{args.label}.png')
    (root/f'.local/windows-{args.label}-verification-dir.txt').write_text(str(work))
    print(json.dumps({'status':report['status'],'sha256':report['sha256'],'checks':len(result['checks']),'gui_seconds':elapsed},indent=2))
if __name__=='__main__': main()
