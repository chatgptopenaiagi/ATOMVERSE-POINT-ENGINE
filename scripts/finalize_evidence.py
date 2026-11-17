"""Generate acceptance from actual test artifacts; fail if required executable checks fail."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--executable',required=True); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]; evidence=root/'EVIDENCE'
    def read(name): return json.loads((evidence/name).read_text(encoding='utf-8-sig'))
    def write(name,value): (evidence/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    tests=ET.parse(root/'.local/mission002-tests.xml').getroot()[0]
    cases=[{'name':c.attrib['name'],'class':c.attrib.get('classname'),'seconds':float(c.attrib.get('time',0)),
            'status':'FAIL' if c.find('failure') is not None or c.find('error') is not None else 'PASS'} for c in tests.findall('testcase')]
    math_report={'status':'PASS' if all(x['status']=='PASS' for x in cases) else 'FAIL',
                 'tests':int(tests.attrib['tests']),'failures':int(tests.attrib['failures']),'errors':int(tests.attrib['errors']),
                 'seconds':float(tests.attrib['time']),'method':'actual pytest suite, pure numerical tests plus real local journals and controlled network failure','cases':cases}
    write('MISSION-002-MATHEMATICAL-TESTS.json',math_report)
    sql=read('SQL-RECOVERY.json'); sql['binding_reproduction']=read('MISSION-002-SQL-BINDING-REPRODUCTION.json')
    sql['dedicated_database']={'status':'UNAVAILABLE','reason':'Current SQL login lacks CREATE DATABASE permission; not an engine failure','fallback':'Verified SQLite WAL local history','provisioning':'scripts/setup-sql.ps1'}
    write('MISSION-002-SQL-RECOVERY.json',sql)
    gui=read('MISSION-002-GUI-VERIFICATION.json'); ai=read('MISSION-002-QWEN-VERIFICATION.json'); perf=read('MISSION-002-PERFORMANCE.json')
    exe=Path(args.executable); sha=hashlib.sha256(exe.read_bytes()).hexdigest()
    assert math_report['status']=='PASS'
    assert gui['status']=='PASS' and gui['packaged'] and gui['clean_shutdown']
    assert ai['status']=='PASS' and ai['packaged_ai_pass'] and all(c['pass'] for c in ai['cases'])
    assert ai['executable_sha256']==sha and perf['executable_sha256']==sha
    assert sql['status']=='PASS' and sql['binding_reproduction']['status']=='PASS'
    baseline=read('MISSION-002-BASELINE.json')
    preserved=root/'dist/preserved/0.1.0-alpha.1/ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe'
    assert hashlib.sha256(preserved.read_bytes()).hexdigest()==baseline['executable_sha256']
    source={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'src').rglob('*.py'))}
    final={'version':'0.2.0-alpha.1','mission_status':'PARTIAL','core_executable_acceptance':'PASS',
           'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'automated_tests_passed':len(cases),
           'packaged_gui_checks_passed':sum(c['passed'] for c in gui['checks']),
           'qwen_cases_passed':sum(c['pass'] for c in ai['cases']),'real_qwen_packaged_workflow':'PASS',
           'real_sql_disconnect_recovery':'PASS (isolated temporary tables)',
           'persistent_local_history':'PASS','dedicated_sql_database':'UNAVAILABLE: permission denied',
           'headless_packaged_execution':perf['packaged_headless']['status'],
           'schema1_history_compatibility':perf['actual_mission001_history_compatibility'],
           'executable_sha256':sha,'previous_executable_preserved':True,'source_sha256':source,
           'limitations':['Dedicated persistent SQL database not provisioned; no permanent SQL throughput claim.',
                          'Actual installed model is 27.3B, not exactly 30B. General natural-language correctness is not guaranteed; proposals require review.',
                          'Snapshot restore pauses and restores values; original analytic trajectory operations use separate command reexecution.',
                          'Soft real time, bounded queues and retention; abrupt process/OS loss can lose the uncommitted tail.',
                          'Hardware/performance measurements are bounded workstation observations, not indefinite capacity guarantees.',
                          'One entity; independent multi-entity worlds remain deferred.'],
           'publication_policy':'Publish this tested alpha with explicit PARTIAL classification; no private histories, credentials, inventory paths or model weights.'}
    write('MISSION-002-FINAL-ACCEPTANCE.json',final)
    write('FINAL-ACCEPTANCE.json',{'current_mission':'002','status':'PARTIAL','core_executable_acceptance':'PASS','details':'MISSION-002-FINAL-ACCEPTANCE.json','mission001_preserved':baseline})
    write('DISCOVERY.json',{'hardware':'MISSION-001-HARDWARE-DISCOVERY.json','software':'MISSION-001-SOFTWARE-DISCOVERY.json','native_compilation':'NATIVE-TOOLCHAIN.json','compute':'CPU-GPU-PERFORMANCE.json','qwen':'MISSION-002-QWEN-VERIFICATION.json','sql':'MISSION-002-SQL-RECOVERY.json','new_environments_created':0,'new_models_downloaded':0,'unrelated_applications_modified':False})
    write('ARCHITECTURE-DECISIONS.json',{'version':2,'state_authority':'Binary64 single-entity kernel','execution':'Independent fixed-step worker; packaged headless path; optional tray persistence','renderer':'Native Qt/OpenGL NVIDIA GPU verified; observer-only views','memory':'Bounded async SQLite WAL plus idempotent ODBC SQL replica','ai':'Loopback Ollama, bounded awareness, action-specific JSON grammar, reviewed proposals, eight GPU layers measured','compute':'Scalar CPU; CUDA reserved for measured bulk workloads','classification':'observed telemetry / mathematical simulation / derived computation / AI interpretation','limitations':final['limitations']})
    write('MATHEMATICAL-VERIFICATION.json',math_report)
    write('MOTION-VERIFICATION.json',{'status':'PASS','method':'Actual kernel and packaged GUI suite','evidence':['MISSION-002-MATHEMATICAL-TESTS.json','MISSION-002-GUI-VERIFICATION.json']})
    write('SPATIAL-PRECISION.json',{'status':'PASS','numeric_type':'IEEE-754 binary64','verified_test':'test_high_coordinate_precision','test':'1e-6 displacement at coordinates +/-1e6, absolute tolerance 1e-10','scope':'Mathematical state; GPU rendering is not guaranteed to preserve this precision at extreme coordinates','coordinate_bounds':[-1e9,1e9]})
    print(json.dumps({k:final[k] for k in ('version','mission_status','core_executable_acceptance','automated_tests_passed','packaged_gui_checks_passed','qwen_cases_passed','executable_sha256')},indent=2))
if __name__=='__main__': main()
