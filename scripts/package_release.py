"""Package an accepted candidate without overwriting any previous executable."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--executable',required=True); args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; executable=Path(args.executable).resolve()
    assert executable.is_relative_to(root/'dist/candidates')
    version=(root/'VERSION').read_text().strip(); assert re.fullmatch(r'\d+\.\d+\.\d+-alpha\.\d+',version)
    acceptance=json.loads((root/'EVIDENCE/MISSION-002-FINAL-ACCEPTANCE.json').read_text())
    assert acceptance['core_executable_acceptance']=='PASS' and acceptance['executable_sha256']==digest(executable)
    release_root=root/'dist/releases'/version; assert not release_root.exists(), 'Refusing to overwrite release artifacts'
    release_root.mkdir(parents=True); application=release_root/'ATOMVERSE-POINT-ENGINE'; shutil.copytree(executable.parent,application)
    for name in ('CONCEPT','ARCHITECTURE','SPECIFICATIONS','RESEARCH','EVIDENCE','migrations'): shutil.copytree(root/name,application/name)
    (application/'scripts').mkdir(); shutil.copy2(root/'scripts/setup-sql.ps1',application/'scripts/setup-sql.ps1')
    for name in ('README.md','ARCHITECTURE.md','ROADMAP.md','VERSION','LICENSE-DECISION.md','THIRD-PARTY-NOTICES.md'): shutil.copy2(root/name,application/name)
    files={str(f.relative_to(application)).replace('\\','/'):{'bytes':f.stat().st_size,'sha256':digest(f)} for f in sorted(application.rglob('*')) if f.is_file()}
    manifest_dir=root/'RELEASES'/version; manifest_dir.mkdir(parents=True,exist_ok=True)
    (manifest_dir/'bundle-files.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    archive=release_root/f'ATOMVERSE-POINT-ENGINE-{version}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(application.rglob('*')):
            if f.is_file(): z.write(f,f.relative_to(release_root))
    extracted=root/'.local'/('extracted-'+version); assert not extracted.exists(), 'Extraction destination already exists'
    with zipfile.ZipFile(archive) as z: z.extractall(extracted)
    extracted_exe=extracted/'ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe'
    assert digest(extracted_exe)==digest(executable)
    for relative,expected in files.items(): assert digest(extracted/'ATOMVERSE-POINT-ENGINE'/relative)==expected['sha256']
    result_path=root/'.local/release-extraction-result.json'
    process=subprocess.run([str(extracted_exe),'--headless','--seconds','1','--no-sql','--data-dir',str(root/'.local/release-extraction-data'),'--snapshot-out',str(result_path)],timeout=15)
    result=json.loads(result_path.read_text()); assert process.returncode==0 and result['status']=='PASS' and result['state']['tick']>100
    pe=executable.read_bytes(); offset=struct.unpack_from('<I',pe,0x3c)[0]; machine=struct.unpack_from('<H',pe,offset+4)[0]; assert machine==0x8664
    sums=digest(archive)+'  '+archive.name+'\n'+digest(executable)+'  ATOMVERSE-POINT-ENGINE.exe\n'
    (manifest_dir/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    report={'status':'PASS','version':version,'architecture':'Windows x64 / PE machine 0x8664','archive_name':archive.name,
            'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive),'executable_sha256':digest(executable),
            'verified_bundle_files':len(files),'all_extracted_hashes_match':True,'extracted_headless_exit_code':process.returncode,
            'extracted_headless_ticks':result['state']['tick'],'previous_artifacts_overwritten':False}
    (root/'EVIDENCE/MISSION-002-PACKAGE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
