"""Capture the unchanged Mission 002 baseline before packaging changes."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

histories = {str(p.relative_to(root)): sha(p) for p in (root / '.local').rglob('*.db')
             if 'mission003' not in str(p)}
(root / '.local/mission003-history-baseline.json').write_text(json.dumps(histories, indent=2))
gui = json.loads((root / '.local/mission003-baseline-gui/gui-verification.json').read_text())
tests = ET.parse(root / '.local/mission003-baseline-tests.xml').getroot().find('testsuite')
release = json.loads(subprocess.check_output(['gh','release','view','v0.2.0-alpha.1','--json','assets,url,isDraft'], cwd=root, text=True))
assert gui['status'] == 'PASS' and gui['clean_shutdown']
assert tests.attrib['failures'] == '0' and tests.attrib['errors'] == '0'
report = {'status':'PASS', 'branch':'main', 'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
          'automated_tests':int(tests.attrib['tests']), 'packaged_gui_checks':len(gui['checks']),
          'packaged_clean_shutdown':gui['clean_shutdown'], 'old_release_public':not release['isDraft'],
          'old_release_url':release['url'], 'previous_assets':{a['name']:a['digest'] for a in release['assets']},
          'old_executable_sha256':sha(root/'dist/releases/0.2.0-alpha.1/ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe'),
          'existing_local_histories_snapshotted':len(histories), 'AGENTS.md':'not present in project or parent directories',
          'kernel_schema':2, 'dedicated_sql':'previous permission limitation; recovery will be rechecked',
          'ai':'existing loopback Ollama adapter retained; current release will be reverified'}
(root/'EVIDENCE/MISSION-003-BASELINE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
