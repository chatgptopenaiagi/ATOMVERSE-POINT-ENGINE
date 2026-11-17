import json
import sqlite3
import time
from atomverse_point.history import History,SQLReplicator,replay
from atomverse_point.kernel import Kernel
from atomverse_point.runtime import Runtime

def test_real_local_batches_order_and_exact_replay(tmp_path):
    k=Kernel(120); h=History(tmp_path/'history.db',k.state.point_id,batch_size=64)
    k.submit({'action':'trajectory','trajectory':{'kind':'helix','duration':2}})
    for e in k.drain_events(): h.record(e)
    expected=[]
    for _ in range(240):
        k.step(); s=k.state.snapshot(); expected.append(s); h.sample(s)
        for e in k.drain_events(): h.record(e)
    assert h.flush(); h.close()
    with sqlite3.connect(h.path) as c:
        rows=c.execute('SELECT seq,monotonic_ns,utc_ns,payload FROM events WHERE kind=\'sample\' ORDER BY seq').fetchall()
        assert len(rows)==240
        assert [r[1] for r in rows]==sorted(r[1] for r in rows)
        assert all(rows[i][0]<rows[i+1][0] for i in range(len(rows)-1))
        assert all(r[2]>0 for r in rows)
        actual=[json.loads(r[3]) for r in rows]
    assert [s['position'] for s in actual]==[list(s['position']) for s in expected]
    assert h.batches<len(rows) and h.samples_written==240
    assert len(replay(h.path,h.session_id))>=240

def test_bounded_capture_reports_gaps_and_preserves_commands(tmp_path):
    k=Kernel(); h=History(tmp_path/'small.db',k.state.point_id,spool_bytes=1)
    h.sample(k.state.snapshot()); h.flush()
    for _ in range(100): h.sample(k.state.snapshot())
    k.submit({'action':'appearance','radius':2})
    for e in k.drain_events(): h.record(e)
    h.close()
    with sqlite3.connect(h.path) as c:
        assert c.execute("SELECT COUNT(*) FROM events WHERE kind='command'").fetchone()[0]==1
        gaps=c.execute("SELECT payload FROM events WHERE kind='capture_gap'").fetchall()
        assert sum(json.loads(x[0])['dropped_samples'] for x in gaps)==h.dropped>0

def test_actual_network_disconnect_keeps_journal_and_terminates(tmp_path):
    k=Kernel(); h=History(tmp_path/'offline.db',k.state.point_id)
    sql=SQLReplicator(h.path,'DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1;DATABASE=ATOMVERSE_POINT_ENGINE;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;')
    r=Runtime(k,h,120); r.start(); r.submit({'action':'velocity','velocity':[1,0,0]}); time.sleep(.2)
    r.close(); sql.close(); h.close()
    assert r.read()['position'][0]>0 and h.samples_written>0
    assert sql.rows==0 and not r.thread.is_alive() and not sql.thread.is_alive() and not h.thread.is_alive()
    assert not r.error

def test_schema_migration_idempotence_and_session_separation(tmp_path):
    path=tmp_path/'history.db'
    first=History(path,'first'); first.sample(Kernel().state.snapshot()); first.close()
    second=History(path,'second'); second.sample(Kernel().state.snapshot()); second.close()
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM sessions').fetchone()[0]==2
    assert len(replay(path,first.session_id))==len(replay(path,second.session_id))==1
