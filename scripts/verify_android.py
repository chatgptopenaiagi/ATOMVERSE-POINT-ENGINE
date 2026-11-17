"""Actual ARM64 APK install, native UI, ADB touch, lifecycle and numerical verification."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

def main():
    p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--apk',required=True);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; apk=Path(args.apk).resolve(); package='org.atomverse.pointengine';activity=package+'/.MainActivity'
    def adb(*parts,timeout=40,check=True):
        process=subprocess.run(['adb','-s',args.serial,*parts],capture_output=True,timeout=timeout)
        if check: assert process.returncode==0,process.stderr.decode(errors='replace')
        return process.stdout
    def report():
        return json.loads(adb('shell','cat','/sdcard/Android/data/'+package+'/files/verification.json'))
    def capture():
        token=uuid.uuid4().hex
        adb('shell','am','start','-n',activity,'--ez','capture','true','--es','capture_id',token)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                result=report()
                if result.get('capture_id')==token:return result
            except (AssertionError,ValueError):pass
            time.sleep(.2)
        raise AssertionError('Capture completion timeout')
    last_tree=None
    def hierarchy():
        nonlocal last_tree
        adb('shell','uiautomator','dump','/sdcard/atomverse-test-ui.xml')
        last_tree=ET.fromstring(adb('shell','cat','/sdcard/atomverse-test-ui.xml'))
        return last_tree
    def tap(label, cached=False):
        for attempt in range(7):
            tree=last_tree if cached and last_tree is not None and attempt==0 else hierarchy()
            for n in tree.iter('node'):
                if n.get('text','').lower()==label.lower():
                    x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')))
                    if y2-y1>30:
                        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.25);return
            adb('shell','input','swipe','530','2180','530','1650','350');time.sleep(.3)
        raise AssertionError('Native button not found: '+label)
    try: previous_session=report()['snapshot']['history']['session_id']
    except (AssertionError,ValueError,KeyError): previous_session=None
    adb('shell','am','force-stop',package)
    installed=adb('install','-r',str(apk),timeout=90).decode();assert 'Success' in installed
    launch=adb('shell','am','start','-W','-n',activity,'--ez','verify','true').decode();assert 'Status: ok' in launch
    deadline=time.monotonic()+35
    first=None
    while time.monotonic()<deadline:
        try:
            first=report()
            if first.get('checks') and len(first['checks'])>=10 and first.get('capture_id') is None and first['snapshot']['history']['session_id']!=previous_session:break
        except (AssertionError,ValueError):pass
        time.sleep(.3)
    assert first and first['status']=='PASS',first
    # Confirm this process has completed its current verification, not just an older file.
    first=capture();assert first['status']=='PASS' and len(first['checks'])==10
    assert first['sqlite']['integrity']=='ok'
    windows=json.loads((root/'EVIDENCE/MISSION-003-WINDOWS-STANDALONE.json').read_text())['vectors']
    differences=[]
    def compare(a,b):
        if isinstance(a,dict):
            assert a.keys()==b.keys()
            for key in a:compare(a[key],b[key])
        elif isinstance(a,(tuple,list)):
            assert len(a)==len(b)
            for x,y in zip(a,b):compare(x,y)
        elif isinstance(a,(float,int)):
            differences.append(abs(a-b));assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10),(a,b)
        else:assert a==b
    compare(windows,first['vectors'])
    tap('Teleport');absolute=capture();assert absolute['snapshot']['state']['position']==[1,2,-3]
    tap('Move by XYZ',cached=True);relative=capture();assert relative['snapshot']['state']['position']==[2,4,-6]
    before=relative['snapshot']['state']['position']
    adb('shell','input','swipe','400','650','700','850','400')
    camera=capture();assert camera['snapshot']['state']['position']==before
    (root/'EVIDENCE/MISSION-003-ANDROID.png').write_bytes(adb('exec-out','screencap','-p'))
    # The live clock intentionally changes accessibility text continuously.
    # Use coordinates inspected in the actual 1080x2400 framebuffer for the
    # lower transport row; UIAutomator's idle wait cannot observe that live UI.
    assert '1080x2400' in adb('shell','wm','size').decode()
    adb('shell','input','swipe','530','2180','530','1560','350');time.sleep(.3)
    adb('shell','input','tap','410','2100');time.sleep(.3)
    adb('shell','input','keyevent','KEYCODE_HOME');time.sleep(1)
    resumed=capture();lifecycle=resumed['snapshot']['lifecycle']
    assert lifecycle['background_count']>=1 and lifecycle['foreground_count']>=1
    assert lifecycle['paused_tick']==lifecycle['foreground_tick'],lifecycle
    adb('shell','input','tap','810','2220');time.sleep(1)
    logs=adb('logcat','-d','-s','ATOMVERSE:I','AndroidRuntime:E').decode(errors='replace')
    assert 'CLEAN_SHUTDOWN' in logs and 'SHUTDOWN_FAILED' not in logs
    restored=capture()
    assert restored['snapshot']['state']['position']==before
    assert restored['sqlite']['integrity']=='ok' and restored['sqlite']['sessions']>first['sqlite']['sessions']
    assert restored['snapshot']['state']['simulation_status']=='PAUSED'
    adb('shell','input','swipe','530','2180','530','1560','350');time.sleep(.3)
    adb('shell','input','tap','810','2220');time.sleep(.5)
    report_data={'status':'PASS','apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'apk_bytes':apk.stat().st_size,
                 'package':package,'version':'0.3.0-alpha.1','native_abi':'arm64-v8a','device_type':'project-owned Android API 37 x86_64 emulator with libndk_translation ARM64 compatibility',
                 'physical_arm64_device':'NOT TESTED','install':'PASS','launch':'PASS','ui_checks':first['checks'],
                 'touch_method':'ADB taps and camera swipe; native hierarchy for initial controls, framebuffer-inspected transport coordinates on 1080x2400 emulator',
                 'adb_touch_absolute_relative':'PASS','camera_independence':'PASS','background_foreground':'PASS','clean_termination':'PASS','restart_restore':'PASS',
                 'sqlite':restored['sqlite'],'python':first['python'],'runtime_during_ui_checks':first['snapshot']['runtime'],
                 'conformance':{'status':'PASS','scenarios':len(windows),'abs_rel_tolerance':1e-10,'maximum_absolute_difference':max(differences)},
                 'vectors':first['vectors'],'launch_measurement':launch,'lifecycle':lifecycle,'history_sessions_before':first['sqlite']['sessions'],'history_sessions_after':restored['sqlite']['sessions']}
    (root/'EVIDENCE/MISSION-003-ANDROID.json').write_text(json.dumps(report_data,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report_data.items() if k not in ('vectors','ui_checks')},indent=2))
if __name__=='__main__':main()
