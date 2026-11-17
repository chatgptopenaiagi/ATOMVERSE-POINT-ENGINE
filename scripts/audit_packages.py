"""Inspect distributable contents and bytecode paths without publishing private paths."""
import argparse
import hashlib
import io
import json
import marshal
from pathlib import Path
import types
import zipfile
from PyInstaller.archive.readers import CArchiveReader

p=argparse.ArgumentParser();p.add_argument('--exe',required=True);p.add_argument('--apk',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];count=0;bad=[]
def inspect(code):
    global count
    if isinstance(code,types.CodeType):
        count+=1
        if 'c:/users/' in code.co_filename.replace('\\','/').lower():bad.append('personal profile in code filename')
        for value in code.co_consts:inspect(value)

exe=CArchiveReader(args.exe)
for name,entry in exe.toc.items():
    if entry[-1]=='z':
        archive=exe.open_embedded_archive(name)
        for module in archive.toc:
            value=archive.extract(module)
            if value:inspect(value)
    elif entry[-1] in ('s','m','M'):inspect(marshal.loads(exe.extract(name)))
license_matches={}
for name in ('BZIP2.txt','OPENSSL.txt','CHAQUOPY.txt','PYTHON.txt'):
    member=next(n for n in exe.toc if n.replace('\\','/').endswith('LICENSES/'+name))
    license_matches[name]=exe.extract(member)==(root/'LICENSES'/name).read_bytes()
with zipfile.ZipFile(args.apk) as apk:
    native={n.split('/')[1] for n in apk.namelist() if n.startswith('lib/') and n.endswith('.so')}
    assert native=={'arm64-v8a'}
    for name in ('BZIP2.txt','OPENSSL.txt','CHAQUOPY.txt','PYTHON.txt'):
        license_matches['android/'+name]=apk.read('assets/'+name)==(root/'LICENSES'/name).read_bytes()
    for name in apk.namelist():
        if name.endswith('.imy'):
            with zipfile.ZipFile(io.BytesIO(apk.read(name))) as nested:
                for member in nested.namelist():
                    if member.endswith('.pyc'):inspect(marshal.loads(nested.read(member)[16:]))
                    if any(part in member.lower() for part in ('.jks','.keystore','.env','history.db')):bad.append('unexpected private file')
report={'status':'PASS' if not bad and all(license_matches.values()) else 'FAIL',
        'bytecode_objects_inspected':count,'personal_path_or_private_file_findings':len(bad),'license_payload_matches':license_matches,
        'android_native_abis':sorted(native),'exe_sha256':hashlib.sha256(Path(args.exe).read_bytes()).hexdigest(),
        'apk_sha256':hashlib.sha256(Path(args.apk).read_bytes()).hexdigest()}
(root/'EVIDENCE/MISSION-003-PACKAGE-AUDIT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2));assert report['status']=='PASS'
