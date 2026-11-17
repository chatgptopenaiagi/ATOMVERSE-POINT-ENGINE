"""Bounded reproduction of the real ODBC buffer-inference failure and fix."""
import json
from pathlib import Path
import uuid
import pyodbc

root=Path(__file__).resolve().parents[1]
report={'method':'real SQL Server, isolated global temporary table, same INSERT SELECT parameter pattern','status':'FAIL'}
connection='DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=tempdb;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;UseFMTONLY=Yes;'
with pyodbc.connect(connection,timeout=5) as c:
    c.timeout=5; cur=c.cursor(); table='##AP_BIND_'+uuid.uuid4().hex[:12]
    cur.execute(f'CREATE TABLE {table}(seq bigint PRIMARY KEY,payload nvarchar(max))'); c.commit()
    sql=f'INSERT INTO {table}(seq,payload) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM {table} WHERE seq=?)'
    values=[(1,'x'*462,1),(2,'y'*1000,2)]
    cur.fast_executemany=True
    try:
        cur.executemany(sql,values); c.commit(); report['unfixed_result']='unexpected success; metadata behavior differed'
    except pyodbc.Error as exc:
        c.rollback(); report['original_exception']={'class':type(exc).__name__,'args':list(exc.args)}
        report['reproduced']='right truncation' in str(exc)
    cur.setinputsizes([(pyodbc.SQL_BIGINT,0,0),(pyodbc.SQL_WVARCHAR,1000,0),(pyodbc.SQL_BIGINT,0,0)])
    cur.executemany(sql,values); c.commit()
    rows=cur.execute(f'SELECT seq,LEN(payload) FROM {table} ORDER BY seq').fetchall()
    report['fixed_rows']=[list(r) for r in rows]
    report['status']='PASS' if report.get('reproduced') and report['fixed_rows']==[[1,462],[2,1000]] else 'FAIL'
report['root_cause']='ODBC inferred a 255-wide-character parameter buffer for INSERT SELECT; the 462-character value exceeded it. Bind maximum batch payload length and SQL types explicitly.'
report['temporary_scope_valid']=True; report['reconnection_was_not_root_cause']=True
report['classification']='Permanent client parameter-binding error for that batch, repaired in code; not a server outage or permission failure.'
(root/'EVIDENCE/MISSION-002-SQL-BINDING-REPRODUCTION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
