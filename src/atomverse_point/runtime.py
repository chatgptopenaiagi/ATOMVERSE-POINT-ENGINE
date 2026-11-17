"""Independent fixed-step worker; snapshots are the GUI's only state interface."""
import queue
import threading
import time
from collections import deque
from .kernel import Kernel
from .model import number, validate_command

class Runtime:
    def __init__(self,kernel,history,record_hz=120,telemetry=None):
        self.kernel=kernel; self.history=history
        self.record_hz=number(record_hz,1,kernel.hz)
        self.commands=queue.Queue(128); self.stop_event=threading.Event()
        self.lock=threading.Lock(); self.snapshot=kernel.state.snapshot()
        self.error=None; self.late_resets=0; self.steps=0; self.busy_ns=0; self.started=time.perf_counter()
        self.next_capture=1/self.record_hz; self.last_command_id=None
        self.telemetry=telemetry; self.telemetry_key=None
        self.command_latency_ms=deque(maxlen=4096); self.update_us=deque(maxlen=4096); self.finished=None
        self.thread=threading.Thread(target=self._run,name='point-simulation',daemon=True)

    def start(self):
        self.started=time.perf_counter()
        self.thread.start()

    def submit(self,c):
        if self.error: raise RuntimeError(self.error)
        validated=validate_command(c)
        try: self.commands.put_nowait((validated,time.perf_counter_ns()))
        except queue.Full as exc: raise ValueError('Command queue is full; command rejected') from exc

    def read(self):
        with self.lock: return dict(self.snapshot)

    def _run(self):
        deadline=time.perf_counter()
        try:
            self.history.sample(self.snapshot)
            while not self.stop_event.is_set():
                busy=time.perf_counter_ns()
                for _ in range(16):
                    try: cmd,enqueued_ns=self.commands.get_nowait()
                    except queue.Empty: break
                    self.command_latency_ms.append((time.perf_counter_ns()-enqueued_ns)/1e6)
                    self.last_command_id=self.kernel.submit(cmd)
                    self.commands.task_done()
                if self.telemetry:
                    measurement=self.telemetry.read()
                    key=(measurement['sequence'],measurement['fresh']) if measurement else None
                    if key is not None and key!=self.telemetry_key:
                        self.kernel.observe_telemetry(measurement); self.telemetry_key=key
                update_started=time.perf_counter_ns()
                self.kernel.step(); self.steps+=1
                self.update_us.append((time.perf_counter_ns()-update_started)/1000)
                for event in self.kernel.drain_events(): self.history.record(event)
                snap=self.kernel.state.snapshot()
                if snap['sim_time']+1e-12>=self.next_capture:
                    self.history.sample(snap)
                    self.next_capture+=1/self.record_hz
                with self.lock: self.snapshot=snap
                self.busy_ns+=time.perf_counter_ns()-busy
                deadline+=self.kernel.dt
                delay=deadline-time.perf_counter()
                if delay<-.25:
                    # Never skip mathematical ticks. Slow simulation wall time explicitly.
                    self.late_resets+=1; deadline=time.perf_counter()
                    self.history.record({'kind':'timing_overrun','tick':snap['tick'],'sim_time':snap['sim_time'],'payload':{'wall_lag_seconds':-delay,'policy':'slow simulation; no skipped ticks'}})
                elif delay>0:
                    # Python's Windows sleep uses a high-resolution waitable timer.
                    # Event.wait measured ~15 ms on this host even for a 4.17 ms delay.
                    while not self.stop_event.is_set():
                        remaining=deadline-time.perf_counter()
                        if remaining<=0: break
                        time.sleep(min(remaining,.01))
        except Exception as exc:
            self.error=f'{type(exc).__name__}: {exc}'
            self.kernel.state.simulation_status='FAULT'
            with self.lock: self.snapshot=self.kernel.state.snapshot()
        finally: self.finished=time.perf_counter()

    def close(self):
        self.stop_event.set()
        if self.thread.ident is not None: self.thread.join(5)
        if self.thread.is_alive(): raise RuntimeError('Simulation shutdown deadline exceeded')

    def stats(self):
        elapsed=max(.001,(self.finished or time.perf_counter())-self.started)
        latencies=sorted(self.command_latency_ms); updates=list(self.update_us)
        return {'worker_iterations_hz':self.steps/elapsed,'worker_cpu_equivalent_percent':self.busy_ns/1e9/elapsed*100,
                'timing_overruns':self.late_resets,'error':self.error,'command_count_measured':len(latencies),
                'command_latency_p95_ms':latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else None,
                'command_latency_max_ms':max(latencies) if latencies else None,
                'mean_kernel_update_us':sum(updates)/max(1,len(updates))}
