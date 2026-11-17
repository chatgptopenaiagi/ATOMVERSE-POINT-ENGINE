"""Install/uninstall the actual wheel in a fresh environment, outside the source tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

def main():
    p=argparse.ArgumentParser(); p.add_argument('--python',required=True); p.add_argument('--wheel',required=True); p.add_argument('--label',required=True); args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; wheel=Path(args.wheel).resolve()
    work=Path(tempfile.mkdtemp(prefix='atomverse-wheel-')); env_dir=work/'venv'
    env=dict(os.environ); env.pop('PYTHONPATH',None); env.pop('PYTHONHOME',None)
    logs=[]
    def run(cmd, expected=0, timeout=120):
        result=subprocess.run([str(x) for x in cmd],cwd=work,env=env,text=True,capture_output=True,timeout=timeout)
        logs.append({'code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode==expected, result.stdout+result.stderr
        return result.stdout
    run([args.python,'-m','venv',env_dir])
    python=env_dir/'Scripts/python.exe'; cli=env_dir/'Scripts/atomverse-point.exe'
    run([python,'-m','pip','install','--no-index','--no-deps',wheel])
    version=run([cli,'--version']).strip()
    run([cli,'--help'])
    run([cli,'--gui'],expected=2)
    run([cli,'--conformance-out',work/'vectors.json'])
    run([cli,'--seconds','.3','--sql','--data-dir',work/'data'])
    result=json.loads((work/'data/headless-result.json').read_text())
    assert result['status']=='PASS' and result['state']['tick']>20
    assert result['sql_status']=='UNAVAILABLE / LOCAL JOURNAL'
    code="""import importlib.util,json,sqlite3,sys
from pathlib import Path
import atomverse_point as a
from atomverse_point.ai import propose
assert Path(a.__file__).is_relative_to(Path(sys.prefix))
assert all(importlib.util.find_spec(n) is None for n in ('PySide6','psutil','pyodbc'))
k=a.Kernel(); k.submit({'action':'teleport','position':[-1,2,3]}); assert k.state.position==(-1.,2.,3.)
r=json.loads(Path('data/headless-result.json').read_text())
assert a.replay('data/history.db',r['history']['session_id'])
with sqlite3.connect('data/history.db') as c: assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
try: propose('move', k.state.snapshot(),endpoint='http://127.0.0.1:1',timeout=.2)
except OSError: pass
else: raise AssertionError('Expected unavailable inference endpoint')
assert not any(n.startswith('PySide6') for n in sys.modules)
print(json.dumps({'python':sys.version.split()[0],'kernel_import':'PASS','optional_dependencies_absent':True,'sqlite_integrity':'ok','ai_unavailable':'PASS'}))
"""
    checks=json.loads(run([python,'-c',code]))
    run([python,'-m','pip','install','pytest==9.1.1','jsonschema==4.26.0'])
    shutil.copytree(root/'tests',work/'tests',ignore=shutil.ignore_patterns('__pycache__'))
    run([python,'-m','pytest','-q','tests','--junitxml=wheel-tests.xml'])
    run([python,'-m','pip','check'])
    run([python,'-m','pip','uninstall','-y','atomverse-point-engine'])
    run([python,'-c',"import importlib.util; assert importlib.util.find_spec('atomverse_point') is None"])
    assert not cli.exists() and (work/'data/history.db').is_file()
    import xml.etree.ElementTree as ET
    tests=ET.parse(work/'wheel-tests.xml').getroot().find('testsuite').attrib
    with zipfile.ZipFile(wheel) as z:
        assert not any(n.lower().endswith(('.dll','.pyd','.exe','.so')) for n in z.namelist())
        wheel_metadata=z.read(next(n for n in z.namelist() if n.endswith('.dist-info/WHEEL'))).decode()
        assert 'Root-Is-Purelib: true' in wheel_metadata and 'Tag: py3-none-any' in wheel_metadata
    report={'status':'PASS','version':version,'wheel':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),
            'fresh_environment':True,'outside_source_tree':True,'tests_passed':int(tests['tests']),
            'cli':'PASS','uninstall':'PASS','history_preserved_after_uninstall':True,'wheel_tags':'py3-none-any',
            'native_payload_files':0,'checks':checks,'vectors':json.loads((work/'vectors.json').read_text())}
    (root/f'.local/wheel-{args.label}-log.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
    (root/f'EVIDENCE/MISSION-003-WHEEL-{args.label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='vectors'},indent=2))
if __name__=='__main__': main()
