"""Opt-in bounded OS/NVIDIA observation, outside the simulation and renderer."""
import copy
import os
import shutil
import subprocess
import threading
import time
import psutil

class Telemetry:
    def __init__(self):
        self.enabled=False; self.stop_event=threading.Event(); self.lock=threading.Lock()
        self.packet=None; self.sequence=0; self.error=None
        self.thread=threading.Thread(target=self._run,name='point-hardware-observer',daemon=True); self.thread.start()
    def read(self):
        with self.lock: packet=copy.deepcopy(self.packet)
        if packet:
            packet['fresh']=self.enabled and time.perf_counter_ns()-packet['monotonic_ns']<3_000_000_000
        return packet
    def _run(self):
        psutil.cpu_percent(None)
        nvidia=shutil.which('nvidia-smi')
        while not self.stop_event.wait(.5):
            if not self.enabled: continue
            values={'cpu_utilization':psutil.cpu_percent(None),'memory_utilization':psutil.virtual_memory().percent}
            unavailable={}
            try:
                freq=psutil.cpu_freq()
                if freq and freq.current>0: values['cpu_clock_mhz']=freq.current
            except (OSError,NotImplementedError): unavailable['cpu_clock_mhz']='OS interface unavailable'
            if nvidia:
                try:
                    result=subprocess.run([nvidia,'--query-gpu=utilization.gpu,power.draw,clocks.current.graphics','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    if result.returncode==0:
                        for name,value in zip(('gpu_utilization','gpu_power_watts','gpu_clock_mhz'),result.stdout.splitlines()[0].split(',')):
                            try: values[name]=float(value.strip())
                            except ValueError: unavailable[name]='GPU driver reports unavailable'
                    else: unavailable['gpu']='nvidia-smi failed'
                except (OSError,subprocess.TimeoutExpired,IndexError): unavailable['gpu']='GPU observation timed out or unavailable'
            else: unavailable['gpu']='NVIDIA observation tool unavailable'
            self.sequence+=1
            packet={'classification':'OBSERVED_TELEMETRY','values':values,'unavailable':unavailable,
                    'utc_ns':time.time_ns(),'monotonic_ns':time.perf_counter_ns(),'sequence':self.sequence,'fresh':True,
                    'sources':{'cpu_utilization':'psutil / OS utilization counters','memory_utilization':'psutil / OS committed physical memory ratio',
                               'cpu_clock_mhz':'psutil / OS clock report','gpu':'nvidia-smi / NVIDIA driver; first GPU'},
                    'units':{'cpu_utilization':'percent','memory_utilization':'percent','gpu_utilization':'percent','gpu_power_watts':'W (driver-reported board power)','cpu_clock_mhz':'MHz','gpu_clock_mhz':'MHz'}}
            with self.lock: self.packet=packet
    def close(self):
        self.stop_event.set(); self.thread.join(4)
        if self.thread.is_alive(): raise RuntimeError('Hardware observer shutdown deadline exceeded')
