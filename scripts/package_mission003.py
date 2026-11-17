"""Gate and assemble Mission 003. Never overwrite an existing release directory."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

root=Path(__file__).resolve().parents[1]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def read(name):return json.loads((root/'EVIDENCE'/name).read_text())
def compare(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for key in a:compare(a[key],b[key])
    elif isinstance(a,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):compare(x,y)
    elif isinstance(a,(float,int)): assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10),(a,b)
    else:assert a==b

def main():
    version=(root/'VERSION').read_text().strip();assert version=='0.3.0-alpha.1'
    reports={label:read('MISSION-003-'+label+'.json') for label in ['WINDOWS-STANDALONE','WINDOWS-PORTABLE','WHEEL-PY314','WHEEL-PY315','ANDROID','AI','SQL-RECOVERY','PACKAGE-AUDIT']}
    assert all(r['status']=='PASS' for r in reports.values())
    onefile=Path((root/'.local/latest-onefile.txt').read_text().strip())
    portable=Path((root/'.local/latest-build.txt').read_text().strip())
    wheel=root/'dist/wheels/atomverse_point_engine-0.3.0a1-py3-none-any.whl'
    apk=root/'android/app/build/outputs/apk/release/app-release.apk'
    assert sha(onefile)==reports['WINDOWS-STANDALONE']['sha256']==reports['PACKAGE-AUDIT']['exe_sha256']
    assert sha(portable)==reports['WINDOWS-PORTABLE']['sha256']
    assert sha(wheel)==reports['WHEEL-PY314']['sha256']==reports['WHEEL-PY315']['sha256']
    assert sha(apk)==reports['ANDROID']['apk_sha256']==reports['PACKAGE-AUDIT']['apk_sha256']
    baseline=read('MISSION-003-BASELINE.json')
    previous=root/'dist/releases/0.2.0-alpha.1'
    assert sha(previous/'ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe')==baseline['old_executable_sha256']
    oldzip=previous/'ATOMVERSE-POINT-ENGINE-0.2.0-alpha.1-windows-x64.zip'
    assert 'sha256:'+sha(oldzip)==baseline['previous_assets'][oldzip.name]
    histories=json.loads((root/'.local/mission003-history-baseline.json').read_text())
    for relative,expected in histories.items():
        path=root/relative;assert sha(path)==expected
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert sha(path)==expected
    reference=reports['WINDOWS-STANDALONE']['vectors']
    for label in ('WINDOWS-PORTABLE','WHEEL-PY314','WHEEL-PY315','ANDROID'):compare(reference,reports[label]['vectors'])
    tests=ET.parse(root/'.local/mission003-tests.xml').getroot().find('testsuite').attrib
    assert tests['failures']=='0' and tests['errors']=='0' and int(tests['tests'])>=78
    acceptance={'status':'PASS','mission':'003','version':version,'automated_tests_passed':int(tests['tests']),
                'windows_standalone':'PASS','windows_portable':'PASS','windows_gui_checks_per_build':len(reports['WINDOWS-STANDALONE']['gui']['checks']),
                'wheel_install_cli_uninstall':'PASS','wheel_tested_python':['3.14.9','3.15.2'],'wheel_tests_per_environment':78,
                'android_arm64_apk':'PASS on compatible emulator','android_physical_device':'NOT TESTED',
                'android_lifecycle_touch_history':'PASS','cross_platform_scenarios':8,'numerical_abs_rel_tolerance':1e-10,
                'previous_release_artifacts':'PASS: byte-identical','existing_sqlite_histories_preserved':len(histories),
                'existing_sqlite_integrity':'PASS','real_qwen_cases_passed':3,'real_sql_recovery':'PASS: isolated temporary resources',
                'dedicated_sql_database':'UNAVAILABLE: provisioning permission required','linux_macos_execution':'NOT TESTED',
                'artifact_sha256':{'standalone_exe':sha(onefile),'portable_exe':sha(portable),'wheel':sha(wheel),'android_apk':sha(apk)},
                'limits':['Android verification uses ARM64 translation on an API 37 emulator, not a physical ARM64 phone.',
                          'Windows is unsigned. Android uses a project-local signing key; no key is published.',
                          'No Android SQL replication, hardware telemetry mapping or AI UI is included.',
                          'The wheel needs Python; GUI, SQL and telemetry remain optional extras.',
                          'Bounded performance observations are not indefinite throughput or hard-real-time guarantees.'],
                'source_sha256':{str(p.relative_to(root)).replace('\\','/'):sha(p) for p in sorted((root/'src').rglob('*.py'))}}
    (root/'EVIDENCE/MISSION-003-FINAL-ACCEPTANCE.json').write_text(json.dumps(acceptance,indent=2),encoding='utf-8')
    destination=root/'dist/releases'/version;assert not destination.exists(),'Refusing to overwrite an existing release'
    destination.mkdir(parents=True)
    shutil.copy2(onefile,destination/onefile.name);shutil.copy2(wheel,destination/wheel.name)
    apk_name=f'ATOMVERSE-POINT-ENGINE-{version}-android-arm64.apk';shutil.copy2(apk,destination/apk_name)
    app=destination/'ATOMVERSE-POINT-ENGINE';shutil.copytree(portable.parent,app)
    for folder in ('CONCEPT','ARCHITECTURE','SPECIFICATIONS','RESEARCH','EVIDENCE','migrations'):
        shutil.copytree(root/folder,app/folder)
    shutil.copytree(root/'LICENSES',app/'LICENSES',dirs_exist_ok=True)
    for name in ('README.md','ARCHITECTURE.md','ROADMAP.md','THIRD-PARTY-NOTICES.md','LICENSE-DECISION.md','VERSION'):
        shutil.copy2(root/name,app/name)
    (app/'scripts').mkdir(exist_ok=True);shutil.copy2(root/'scripts/setup-sql.ps1',app/'scripts/setup-sql.ps1')
    files={str(p.relative_to(app)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(app.rglob('*')) if p.is_file()}
    archive=destination/f'ATOMVERSE-POINT-ENGINE-{version}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(app.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(destination))
    extracted=Path(tempfile.mkdtemp(prefix='atomverse-final-zip-'))
    with zipfile.ZipFile(archive) as z:z.extractall(extracted)
    for name,value in files.items():assert sha(extracted/'ATOMVERSE-POINT-ENGINE'/name)==value['sha256']
    process=subprocess.run([str(extracted/'ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe'),'--headless','--seconds','.5','--no-sql','--data-dir',str(extracted/'data')],cwd=extracted,timeout=30)
    assert process.returncode==0 and json.loads((extracted/'data/headless-result.json').read_text())['status']=='PASS'
    artifacts=[destination/onefile.name,destination/wheel.name,destination/apk_name,archive]
    sums=''.join(sha(p)+'  '+p.name+'\n' for p in artifacts)
    manifest_name=f'ATOMVERSE-POINT-ENGINE-{version}-SHA256SUMS.txt'
    (destination/manifest_name).write_text(sums,encoding='utf-8')
    release_docs=root/'RELEASES'/version;release_docs.mkdir(parents=True,exist_ok=True)
    (release_docs/manifest_name).write_text(sums,encoding='utf-8')
    (release_docs/'bundle-files.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    package={'status':'PASS','version':version,'portable_files_verified':len(files),'extracted_portable_execution':'PASS',
             'artifacts':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in artifacts},'previous_release_overwritten':False}
    (root/'EVIDENCE/MISSION-003-PACKAGE.json').write_text(json.dumps(package,indent=2),encoding='utf-8')
    print(json.dumps(package,indent=2))
if __name__=='__main__':main()
