"""Bounded asynchronous journal and idempotent SQL Server replication.

SQLite WAL is the durable local journal, not the simulation's state authority.
No rendering or simulation callback performs a database operation.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import queue
import re
import sqlite3
import threading
import time
import uuid

SQL_CONNECTION = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
                  'DATABASE=ATOMVERSE_POINT_ENGINE;Trusted_Connection=yes;'
                  'Encrypt=yes;TrustServerCertificate=yes;')

LOCAL_SCHEMA = '''
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_migrations VALUES(1);
CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY, point_id TEXT NOT NULL,
 created_ns INTEGER NOT NULL, config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(session_id TEXT NOT NULL, seq INTEGER NOT NULL,
 kind TEXT NOT NULL, tick INTEGER NOT NULL, sim_time REAL NOT NULL, utc_ns INTEGER NOT NULL,
 monotonic_ns INTEGER NOT NULL, payload TEXT NOT NULL, replicated INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(session_id,seq));
CREATE INDEX IF NOT EXISTS pending_replication ON events(replicated,session_id,seq);
CREATE INDEX IF NOT EXISTS replay_samples ON events(session_id,kind,seq);
'''

def connect_local(path):
    c=sqlite3.connect(str(path),timeout=5)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=FULL')
    return c

class History:
    def __init__(self,path,point_id,config=None,capacity=8192,batch_size=512,
                 spool_bytes=256*1024*1024,critical_reserve=16*1024*1024):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.session_id=str(uuid.uuid4()); self.point_id=point_id
        self.config=config or {}; self.batch_size=batch_size
        self.spool_bytes=spool_bytes; self.critical_reserve=critical_reserve
        self.queue=queue.Queue(capacity); self.seq=0; self.lock=threading.Lock()
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.written=0; self.samples_written=0; self.dropped=0; self.gap_pending=0
        self.batches=0; self.error=None; self.closed=False; self.total_bytes=0
        self.start_time=time.perf_counter(); self.last_commit_ms=0.
        self.thread=threading.Thread(target=self._run,name='point-journal',daemon=True)
        self.thread.start()
        if not self.ready.wait(10) or self.error: raise RuntimeError('Local journal could not start: '+str(self.error))

    def _packet(self,kind,tick,sim_time,payload,utc_ns=None,monotonic_ns=None):
        self.seq+=1
        return (self.session_id,self.seq,kind,tick,sim_time,utc_ns or time.time_ns(),monotonic_ns or time.perf_counter_ns(),json.dumps(payload,separators=(',',':'),allow_nan=False))

    def record(self,event,critical=True):
        if self.closed: raise RuntimeError('Journal is closed')
        with self.lock:
            if not critical and (self.queue.full() or self.total_bytes>=self.spool_bytes):
                self.dropped+=1; self.gap_pending+=1; return False
            if self.error: raise RuntimeError('Journal unavailable: '+self.error)
            if self.gap_pending:
                gap=self._packet('capture_gap',event['tick'],event['sim_time'],{'dropped_samples':self.gap_pending,'policy':'sample queue or local spool capacity exceeded'})
                self.queue.put(gap,timeout=2)
                self.gap_pending=0
            packet=self._packet(event['kind'],event['tick'],event['sim_time'],event['payload'],event.get('utc_ns'),event.get('monotonic_ns'))
            if critical:
                self.queue.put(packet,timeout=2)
            else:
                try: self.queue.put_nowait(packet)
                except queue.Full:
                    self.dropped+=1; self.gap_pending+=1; return False
            return True

    def sample(self,state):
        return self.record({'kind':'sample','tick':state['tick'],'sim_time':state['sim_time'],'payload':state},False)

    def _run(self):
        c=None
        try:
            c=connect_local(self.path); c.executescript(LOCAL_SCHEMA)
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(self.session_id,self.point_id,time.time_ns(),json.dumps(self.config)))
            c.commit()
            self.total_bytes=c.execute('SELECT COALESCE(SUM(length(payload)),0) FROM events').fetchone()[0]
            self.ready.set()
            while not self.stop_event.is_set() or not self.queue.empty():
                try: batch=[self.queue.get(timeout=.05)]
                except queue.Empty: continue
                deadline=time.perf_counter()+.025
                while len(batch)<self.batch_size:
                    remaining=deadline-time.perf_counter()
                    if remaining<=0: break
                    try: batch.append(self.queue.get(timeout=remaining))
                    except queue.Empty: break
                batch_bytes=sum(len(p[-1].encode('utf-8')) for p in batch)
                if self.total_bytes+batch_bytes>self.spool_bytes+self.critical_reserve:
                    raise RuntimeError('Local journal retention cap reached; archive this journal and start a new data directory')
                start=time.perf_counter()
                with c:
                    c.executemany('INSERT INTO events(session_id,seq,kind,tick,sim_time,utc_ns,monotonic_ns,payload) VALUES(?,?,?,?,?,?,?,?)',batch)
                self.last_commit_ms=(time.perf_counter()-start)*1000
                self.total_bytes+=batch_bytes; self.written+=len(batch); self.batches+=1
                self.samples_written+=sum(p[2]=='sample' for p in batch)
                for _ in batch: self.queue.task_done()
        except Exception as exc:
            self.error=f'{type(exc).__name__}: {exc}'
            self.ready.set()
            # Preserve the batch that could not commit, where the filesystem permits.
            if 'batch' in locals():
                try:
                    recovery=self.path.with_name('journal-recovery-'+self.session_id+'.json')
                    recovery.write_text(json.dumps(batch),encoding='utf-8')
                except OSError: pass
        finally:
            if c: c.close()

    def flush(self,timeout=10):
        deadline=time.monotonic()+timeout
        while self.queue.unfinished_tasks and time.monotonic()<deadline and not self.error:
            time.sleep(.01)
        return not self.queue.unfinished_tasks and not self.error

    def close(self):
        if self.closed: return
        if self.gap_pending and not self.error:
            self.record({'kind':'recording_end','tick':0,'sim_time':0,'payload':{'dropped_samples_total':self.dropped}})
        self.closed=True; self.stop_event.set(); self.thread.join(10)
        if self.thread.is_alive(): raise RuntimeError('Journal shutdown deadline exceeded')
        if self.error: raise RuntimeError(self.error)

    def stats(self):
        return {'session_id':self.session_id,'written':self.written,'samples_written':self.samples_written,
                'dropped_samples':self.dropped,'queue_depth':self.queue.qsize(),'batches':self.batches,
                'events_per_second':self.written/max(.001,time.perf_counter()-self.start_time),
                'last_commit_ms':self.last_commit_ms,'error':self.error,'payload_bytes':self.total_bytes}

def sessions(path):
    with connect_local(path) as c:
        return c.execute('SELECT session_id,created_ns,config FROM sessions ORDER BY created_ns DESC LIMIT 100').fetchall()

def replay(path,session_id,limit=250000):
    """Exact recorded states; missing samples are never invented or called measurements."""
    with connect_local(path) as c:
        rows=c.execute("SELECT seq,payload FROM events WHERE session_id=? AND kind IN ('sample','state_transition') ORDER BY seq LIMIT ?",(session_id,limit+1)).fetchall()
    if len(rows)>limit: raise ValueError('Replay exceeds bounded session limit; export a smaller session')
    return [dict(json.loads(r[1]),event_seq=r[0]) for r in rows]

class SQLReplicator:
    def __init__(self,path,connection_string=SQL_CONNECTION,batch_size=512,table_prefix='POINT_'):
        if not re.fullmatch(r'(?:##)?[A-Za-z_][A-Za-z0-9_]{0,70}',table_prefix): raise ValueError('Invalid SQL table prefix')
        self.table_prefix=table_prefix
        self.path=Path(path); self.connection_string=connection_string; self.batch_size=batch_size
        self.stop_event=threading.Event(); self.status='CONNECTING'; self.error=None
        self.error_detail=None
        self.rows=0; self.batches=0; self.last_batch_ms=0.
        self.thread=threading.Thread(target=self._run,name='point-sql-replication',daemon=True)
        self.thread.start()

    def _run(self):
        import pyodbc
        local=connect_local(self.path); remote=None
        entities=self.table_prefix+'ENTITIES'; sessions_table=self.table_prefix+'SESSIONS'; events=self.table_prefix+'EVENTS'
        try:
            while not self.stop_event.is_set():
                try:
                    if remote is None:
                        remote=pyodbc.connect(self.connection_string,timeout=3); remote.timeout=3
                        self.status='CONNECTED'; self.error=None
                    session_rows=local.execute('SELECT session_id,point_id,created_ns,config FROM sessions').fetchall()
                    cur=remote.cursor()
                    for sid,pid,created,config in session_rows:
                        cur.execute(f'IF NOT EXISTS(SELECT 1 FROM {entities} WHERE point_id=?) INSERT INTO {entities} VALUES(?)',pid,pid)
                        cur.execute(f'IF NOT EXISTS(SELECT 1 FROM {sessions_table} WHERE session_id=?) INSERT INTO {sessions_table} VALUES(?,?,?,?)',sid,sid,pid,created,config)
                    rows=local.execute('SELECT session_id,seq,kind,tick,sim_time,utc_ns,monotonic_ns,payload FROM events WHERE replicated=0 ORDER BY session_id,seq LIMIT ?',(self.batch_size,)).fetchall()
                    if not rows:
                        remote.commit(); self.stop_event.wait(.1); continue
                    started=time.perf_counter()
                    values=[]
                    for sid,seq,kind,tick,sim,utc,mono,payload in rows:
                        obj=json.loads(payload); pos=obj.get('position',[None,None,None]) if kind in ('sample','state_transition') else [None,None,None]
                        utc_text=dt.datetime.fromtimestamp(utc//1_000_000_000,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+'.'+f'{utc%1_000_000_000:09d}'[:7]
                        values.append((sid,seq,kind,tick,sim,utc,mono,utc_text,*pos,payload,sid,seq))
                    cur.fast_executemany=True
                    # INSERT..SELECT parameter metadata can infer nvarchar(255).
                    # Bind the whole batch's real maximum, not the first row's length.
                    max_payload=max(len(v[11]) for v in values)
                    cur.setinputsizes([
                        (pyodbc.SQL_VARCHAR,36,0),(pyodbc.SQL_BIGINT,0,0),(pyodbc.SQL_VARCHAR,32,0),
                        (pyodbc.SQL_BIGINT,0,0),(pyodbc.SQL_DOUBLE,0,0),(pyodbc.SQL_BIGINT,0,0),
                        (pyodbc.SQL_BIGINT,0,0),(pyodbc.SQL_VARCHAR,32,0),
                        (pyodbc.SQL_DOUBLE,0,0),(pyodbc.SQL_DOUBLE,0,0),(pyodbc.SQL_DOUBLE,0,0),
                        (pyodbc.SQL_WLONGVARCHAR if max_payload>4000 else pyodbc.SQL_WVARCHAR,max_payload,0),
                        (pyodbc.SQL_VARCHAR,36,0),(pyodbc.SQL_BIGINT,0,0)])
                    cur.executemany(f'INSERT INTO {events}(session_id,seq,kind,tick,sim_time,utc_ns,monotonic_ns,utc_time,x,y,z,payload) SELECT ?,?,?,?,?,?,?,CONVERT(datetime2(7),?),?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM {events} WHERE session_id=? AND seq=?)',values)
                    remote.commit()
                    with local: local.executemany('UPDATE events SET replicated=1 WHERE session_id=? AND seq=?',[(r[0],r[1]) for r in rows])
                    self.rows+=len(rows); self.batches+=1; self.last_batch_ms=(time.perf_counter()-started)*1000
                    self.status='CONNECTED'; self.error=None
                except Exception as exc:
                    self.status='OFFLINE / LOCAL JOURNAL'; self.error=type(exc).__name__
                    self.error_detail=str(exc)
                    if remote:
                        try: remote.close()
                        except Exception: pass
                    remote=None; self.stop_event.wait(2)
        finally:
            local.close()
            if remote: remote.close()

    def close(self):
        self.stop_event.set(); self.thread.join(8)
        if self.thread.is_alive(): raise RuntimeError('SQL shutdown deadline exceeded; durable backlog remains local')
