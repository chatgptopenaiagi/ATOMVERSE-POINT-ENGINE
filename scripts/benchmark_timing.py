import json
from pathlib import Path
import threading
import time

root=Path(__file__).resolve().parents[1]; event=threading.Event(); results={}
for name,fn in [('event_wait',event.wait),('python_sleep',time.sleep)]:
    started=time.perf_counter()
    for _ in range(120): fn(1/240)
    results[name+'_mean_ms']=(time.perf_counter()-started)*1000/120
results.update(requested_delay_ms=1000/240,iterations=120,method='actual Windows wall-clock measurements; ordinary machine load',decision='Use Python high-resolution sleep in the fixed-step scheduler; bound shutdown polling to 10 ms; no global timer reconfiguration')
(root/'EVIDENCE/MISSION-002-TIMING.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
