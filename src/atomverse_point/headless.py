"""Entity execution without creating a graphical application or renderer."""
import json
import os
from pathlib import Path
import time
from . import __version__
from .kernel import Kernel
from .history import History,SQLReplicator,SQL_CONNECTION
from .runtime import Runtime

def run(args):
    kernel=Kernel(args.sim_hz)
    history=History(args.data_dir/'history.db',kernel.state.point_id,{'sim_hz':args.sim_hz,'record_hz':args.record_hz,'version':__version__,'mode':'headless'})
    runtime=Runtime(kernel,history,args.record_hz)
    sql=None if args.no_sql else SQLReplicator(history.path,os.environ.get('ATOMVERSE_SQL_CONNECTION',SQL_CONNECTION))
    errors=[]; runtime.start()
    try:
        if args.command_file:
            if args.command_file.stat().st_size>65536: raise ValueError('Command file exceeds 64 KiB')
            commands=json.loads(args.command_file.read_text(encoding='utf-8'))
            if not isinstance(commands,list) or len(commands)>128: raise ValueError('Provide a JSON list of at most 128 commands')
            for command in commands: runtime.submit(command)
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline and not runtime.error: time.sleep(.02)
    except KeyboardInterrupt: pass
    except Exception as exc: errors.append(str(exc))
    finally:
        for part in (runtime,sql,history):
            if part:
                try: part.close()
                except Exception as exc: errors.append(str(exc))
    result={'version':__version__,'headless':True,'renderer_created':False,'state':runtime.read(),'runtime':runtime.stats(),'history':history.stats(),'sql_status':sql.status if sql else 'disabled','errors':errors,'status':'PASS' if not errors and not runtime.error else 'FAIL'}
    destination=args.snapshot_out or args.data_dir/'headless-result.json'
    destination.parent.mkdir(parents=True,exist_ok=True); destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['status']=='PASS' else 1
