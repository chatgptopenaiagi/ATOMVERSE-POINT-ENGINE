"""Android lifecycle adapter. Mathematics and SQLite use the desktop modules unchanged."""
import json
import bisect
from pathlib import Path
import sqlite3
import time
from atomverse_point import Kernel, History, Runtime, replay
from atomverse_point.history import sessions
from atomverse_point.conformance import vectors

engine = None

class Engine:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.kernel = Kernel(120)
        self.history = History(self.directory/'history.db', self.kernel.state.point_id, {'sim_hz':120,'record_hz':60,'platform':'Android'})
        self.runtime = Runtime(self.kernel, self.history, 60)
        self.recorded = []
        self.replay_index = 0
        self.replay_times = []
        self.replay_start = 0
        self.lifecycle = {'background_count':0,'foreground_count':0}
        self.was_running = False
        self.runtime.start()
        saved = self.directory/'last-state.json'
        if saved.is_file():
            self.runtime.submit({'action':'restore','state':json.loads(saved.read_text())})

    def pause(self):
        self.was_running = self.runtime.read()['simulation_status'] != 'PAUSED'
        self.runtime.submit({'action':'pause'})
        deadline = time.monotonic()+1
        while self.runtime.read()['simulation_status'] != 'PAUSED' and time.monotonic()<deadline:
            time.sleep(.01)
        self.save()
        self.history.flush()

    def save(self):
        temp = self.directory/'last-state.tmp'
        temp.write_text(json.dumps(self.runtime.read()), encoding='utf-8')
        temp.replace(self.directory/'last-state.json')

def start(directory):
    global engine
    if engine is None: engine = Engine(directory)
    return snapshot()

def command(raw):
    engine.recorded = []
    engine.runtime.submit(json.loads(raw))

def snapshot():
    if engine is None: return '{}'
    live = engine.runtime.read()
    projected = live
    if engine.recorded:
        elapsed=time.monotonic()-engine.replay_start
        engine.replay_index=max(0,min(len(engine.recorded)-1,bisect.bisect_right(engine.replay_times,engine.replay_times[0]+elapsed)-1))
        projected = engine.recorded[engine.replay_index]
    return json.dumps({'state':live,'projection':projected,'replaying':bool(engine.recorded),
                       'history':engine.history.stats(),'runtime':engine.runtime.stats(),'lifecycle':engine.lifecycle})

def begin_replay():
    engine.runtime.submit({'action':'pause'})
    engine.history.flush()
    choices = sessions(engine.history.path)
    # Prefer this session, otherwise the newest nonempty historical session.
    for sid in [engine.history.session_id]+[row[0] for row in choices]:
        values = replay(engine.history.path,sid)
        if values:
            engine.recorded=values; engine.replay_index=0
            engine.replay_times=[s['sim_time'] for s in values]; engine.replay_start=time.monotonic()
            return len(values)
    return 0

def background():
    if engine:
        engine.pause()
        engine.lifecycle['background_count']+=1
        engine.lifecycle['paused_tick']=engine.runtime.read()['tick']

def foreground():
    if engine:
        engine.lifecycle['foreground_count']+=1
        engine.lifecycle['foreground_tick']=engine.runtime.read()['tick']
        if engine.was_running:
            engine.runtime.submit({'action':'resume'}); engine.was_running=False

def close():
    global engine
    if engine:
        engine.runtime.close(); engine.save(); engine.history.close(); engine=None

def conformance(): return json.dumps(vectors())

def integrity():
    engine.history.flush()
    with sqlite3.connect(str(engine.history.path)) as c:
        return json.dumps({'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],
                           'events':c.execute('SELECT count(*) FROM events').fetchone()[0],
                           'sessions':c.execute('SELECT count(*) FROM sessions').fetchone()[0]})
