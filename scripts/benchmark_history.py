import datetime
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid
import pyodbc
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point.history import History,SQL_CONNECTION,replay
from atomverse_point.kernel import Kernel
from atomverse_point.runtime import Runtime

root=Path(__file__).resolve().parents[1]
report={'measured':True,'sql_server_available':False,'dedicated_database_available':False,'tests':[]}
try:
    c=pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=master;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;UseFMTONLY=Yes;',timeout=5)
    c.timeout=5; cur=c.cursor()
    report['server_version']=str(cur.execute("SELECT SERVERPROPERTY('ProductVersion')").fetchone()[0]); report['sql_server_available']=True
    report['can_create_database']=bool(cur.execute("SELECT HAS_PERMS_BY_NAME(NULL,'SERVER','CREATE ANY DATABASE')").fetchone()[0])
    try:
        db=pyodbc.connect(SQL_CONNECTION,timeout=3); db.close(); report['dedicated_database_available']=True
    except pyodbc.Error as exc: report['dedicated_database_error_sqlstate']=exc.args[0]
    cur.execute('CREATE TABLE #PointBenchmark(seq bigint PRIMARY KEY, tick bigint, utc_ns bigint, utc_time datetime2(7), x float, y float, z float, payload nvarchar(2048))')
    c.commit()
    n=20000; payload=json.dumps(Kernel().state.snapshot()); base=time.time_ns()
    rows=[(i,i,base+i*1000000,datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),float(i),.5,1.,payload) for i in range(n)]
    cur.fast_executemany=True; started=time.perf_counter()
    for offset in range(0,n,512):
        cur.executemany('INSERT INTO #PointBenchmark VALUES(?,?,?,?,?,?,?,?)',rows[offset:offset+512]); c.commit()
    elapsed=time.perf_counter()-started
    count=cur.execute('SELECT COUNT(*) FROM #PointBenchmark').fetchone()[0]
    query_start=time.perf_counter(); fetched=cur.execute('SELECT seq,x,y,z FROM #PointBenchmark ORDER BY seq').fetchall(); query_time=time.perf_counter()-query_start
    assert count==n and len(fetched)==n and fetched[-1][0]==n-1
    report['temporary_table_batch_test']={'rows':n,'batch_size':512,'seconds':elapsed,'rows_per_second':n/elapsed,'ordered_query_seconds':query_time,'count_verified':True,'scope':'real local SQL Server tempdb temporary table; not durable dedicated engine database or disconnect-recovery proof'}
    c.close()
except Exception as exc: report['probe_error']=f'{type(exc).__name__}: '+str(exc.args[0] if exc.args else exc)

proc=psutil.Process()
for hz in (120,240,500,1000,2000):
    directory=root/'.local'/('rate-'+str(hz)+'-'+uuid.uuid4().hex[:8]); directory.mkdir()
    k=Kernel(hz); h=History(directory/'history.db',k.state.point_id,{'sim_hz':hz,'record_hz':hz})
    runtime=Runtime(k,h,hz); before=proc.memory_info().rss; started=time.perf_counter()
    runtime.start(); runtime.submit({'action':'velocity','velocity':[1,2,3]})
    time.sleep(3)
    runtime.close(); wall=time.perf_counter()-started; assert h.flush(); h.close()
    read_start=time.perf_counter(); states=replay(h.path,h.session_id); replay_seconds=time.perf_counter()-read_start
    stats=runtime.stats(); snap=runtime.read()
    entry={'requested_hz':hz,'wall_seconds':wall,'ticks':snap['tick'],'actual_ticks_per_second':snap['tick']/wall,
           'simulation_seconds':snap['sim_time'],'wall_minus_sim_seconds':wall-snap['sim_time'],
           'samples_written':h.samples_written,'dropped':h.dropped,'journal_events_per_second':h.written/wall,
           'batch_count':h.batches,'replay_seconds':replay_seconds,'replayed_states':len(states),
           'rss_growth_bytes':proc.memory_info().rss-before,'runtime':stats,'file_bytes':h.path.stat().st_size}
    report['tests'].append(entry); print('Measured capture rate '+str(hz)+' Hz',flush=True)
report['policy']='240 simulation Hz, 120 recording Hz, 60 render target by default. Three-second headless sweeps are bounded observations, not long-duration guarantees. SQLite journal uses 256 MiB payload budget plus 16 MiB critical reserve; sample gaps are explicit.'
(root/'EVIDENCE/SQL-THROUGHPUT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
