import json
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from atomverse_point.app import Window
from atomverse_point.render import surface_format

root=Path(__file__).resolve().parents[1]; destination=root/'.local/projection-views'; destination.mkdir(exist_ok=True)
args=SimpleNamespace(sim_hz=240,record_hz=120,render_hz=60,data_dir=root/'.local/projection-data',no_sql=True,
                     ai_endpoint='http://127.0.0.1:11434',ai_model='qwen3.8:27b',ai_gpu=0,verify_ui=None,keep_running=False,verify_ai=False)
surface_format(); app=QApplication([]); window=Window(args); window.show()
report={'method':'actual source application widgets and framebuffer captures; packaged state-independence separately verified','checks':[]}; stage=0; frozen=None
def advance():
    global stage,frozen
    try:
        if stage==0:
            window.send({'action':'oscillator','enabled':True,'frequency':1,'amplitude':2}); window.projection_choice.setCurrentText('signal')
        elif stage==2: window.send({'action':'pause'})
        elif stage==3: frozen=window.runtime.read(); window.projection_choice.setCurrentText('wave')
        elif 4<=stage<=7:
            mode=['wave','spiral','signal','data'][stage-4]
            assert window.runtime.read()==frozen
            target=destination/(mode+'.png'); window.views.currentWidget().grab().save(str(target))
            assert target.stat().st_size>5000
            report['checks'].append({'view':mode,'state_unchanged':True,'actual_capture_bytes':target.stat().st_size})
            if stage<7: window.projection_choice.setCurrentText(['wave','spiral','signal','data'][stage-3])
            else:
                report['status']='PASS'; timer.stop(); window.shutdown(); return
        stage+=1
    except Exception as exc:
        report.update(status='FAIL',error=str(exc)); timer.stop(); window.shutdown()
timer=QTimer(); timer.timeout.connect(advance); timer.start(500); app.exec()
(root/'EVIDENCE/MISSION-002-PROJECTION-VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
