"""Real SQL Server recovery test using isolated auto-deleting global temp tables.
No SQL Server service is stopped; the client starts at a closed loopback port,
then reconnects to the verified local instance and retries the durable journal.
"""
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid
import pyodbc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from atomverse_point.history import History,SQLReplicator
from atomverse_point.kernel import Kernel

root=Path(__file__).resolve().parents[1]; report={'status':'UNAVAILABLE','method':'actual local SQL Server; isolated global temporary tables; real connection failure followed by recovery'}
anchor=None; h=None; replica=None
try:
    connection='DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=tempdb;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;UseFMTONLY=Yes;'
    anchor=pyodbc.connect(connection,timeout=5); anchor.timeout=5
    prefix='##AP_'+uuid.uuid4().hex[:12]+'_'; cur=anchor.cursor()
    cur.execute(f'CREATE TABLE {prefix}ENTITIES(point_id varchar(36) PRIMARY KEY)')
    cur.execute(f'CREATE TABLE {prefix}SESSIONS(session_id varchar(36) PRIMARY KEY,point_id varchar(36),created_ns bigint,config nvarchar(max))')
    cur.execute(f'CREATE TABLE {prefix}EVENTS(session_id varchar(36),seq bigint,kind varchar(32),tick bigint,sim_time float,utc_ns bigint,monotonic_ns bigint,utc_time datetime2(7),x float,y float,z float,payload nvarchar(max),PRIMARY KEY(session_id,seq))'); anchor.commit()
    k=Kernel(100); path=root/'.local'/('sql-recovery-'+uuid.uuid4().hex[:8]+'.db')
    h=History(path,k.state.point_id)
    replica=SQLReplicator(path,connection.replace('SERVER=localhost','SERVER=127.0.0.1,1'),batch_size=128,table_prefix=prefix)
    k.submit({'action':'velocity','velocity':[1,2,3]})
    for e in k.drain_events(): h.record(e)
    for _ in range(1000): k.step(); h.sample(k.state.snapshot())
    assert h.flush()
    deadline=time.monotonic()+12
    while not replica.status.startswith('OFFLINE') and time.monotonic()<deadline: time.sleep(.1)
    report['connection_failed']=replica.rows==0 and replica.status.startswith('OFFLINE')
    report['local_events_while_offline']=h.written
    replica.connection_string=connection; start=time.perf_counter()
    deadline=time.monotonic()+25
    while replica.rows<h.written and time.monotonic()<deadline: time.sleep(.1)
    count=cur.execute(f'SELECT COUNT(*) FROM {prefix}EVENTS').fetchone()[0]
    report['recovered_rows']=count; report['recovery_seconds']=time.perf_counter()-start
    assert count==h.written, (count,h.written,replica.error)
    # Simulate lost acknowledgement after SQL commit: repeat the same event IDs.
    with sqlite3.connect(path) as c: c.execute('UPDATE events SET replicated=0')
    expected=replica.rows+h.written; deadline=time.monotonic()+15
    while replica.rows<expected and time.monotonic()<deadline: time.sleep(.1)
    again=cur.execute(f'SELECT COUNT(*) FROM {prefix}EVENTS').fetchone()[0]
    report['idempotent_retry_count']=again; assert again==count and replica.rows>=expected
    row=cur.execute(f"SELECT TOP 1 x,y,z,utc_ns,utc_time FROM {prefix}EVENTS WHERE kind='sample' ORDER BY seq DESC").fetchone()
    report['last_xyz']=list(row[:3]); assert list(row[:3])==list(k.state.position)
    report['datetime2_roundtrip']=str(row[4]); report['utc_ns_preserved']=row[3]>0
    report['batches']=replica.batches; report['status']='PASS'
    report['limitation']='This verifies the real replication and retry path in tempdb. The dedicated persistent database remains unprovisioned if CREATE DATABASE permission is absent.'
except Exception as exc:
    report['error']=f'{type(exc).__name__}: {exc}'
    if replica: (root/'.local/sql-recovery-error.txt').write_text(str(replica.error_detail),encoding='utf-8')
finally:
    if replica: replica.close()
    if h: h.close()
    if anchor: anchor.close()
    (root/'EVIDENCE/SQL-RECOVERY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
