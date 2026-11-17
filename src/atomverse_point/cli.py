"""Dependency-free command line; GUI imports happen only on explicit GUI launch."""
import argparse
import json
import os
from pathlib import Path
import sys
from . import __version__


def default_data_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ATOMVERSE-POINT-ENGINE'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/ATOMVERSE-POINT-ENGINE'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'atomverse-point-engine'


def main(argv=None, *, default_gui=False):
    p = argparse.ArgumentParser(description='One computational entity. Headless by default; --gui opens the optional desktop projection.')
    p.add_argument('--version', action='version', version=__version__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--gui', action='store_true')
    mode.add_argument('--headless', action='store_true')
    p.add_argument('--data-dir', type=Path, default=default_data_dir())
    p.add_argument('--sim-hz', type=int, default=240)
    p.add_argument('--record-hz', type=int, default=120)
    p.add_argument('--render-hz', type=int, default=60)
    sql = p.add_mutually_exclusive_group()
    sql.add_argument('--sql', action='store_true', help='Enable optional SQL replication in headless mode')
    sql.add_argument('--no-sql', action='store_true')
    p.add_argument('--verify-ui', type=Path)
    p.add_argument('--verify-ai', action='store_true')
    p.add_argument('--verify-ai-unavailable', action='store_true')
    p.add_argument('--keep-running', action='store_true')
    p.add_argument('--seconds', type=float, default=10)
    p.add_argument('--command-file', type=Path)
    p.add_argument('--snapshot-out', type=Path)
    p.add_argument('--conformance-out', type=Path, help='Run deterministic cross-platform vectors and exit')
    p.add_argument('--ai-endpoint', default='http://127.0.0.1:11434')
    p.add_argument('--ai-model', default='qwen3.8:27b')
    p.add_argument('--ai-gpu', type=int, default=8)
    args = p.parse_args(argv)
    if not 1 <= args.record_hz <= args.sim_hz <= 2000 or not 1 <= args.render_hz <= 144:
        p.error('Require 1 <= record Hz <= simulation Hz <= 2000 and 1 <= rendering Hz <= 144')
    if args.conformance_out:
        from .conformance import vectors
        args.conformance_out.parent.mkdir(parents=True, exist_ok=True)
        args.conformance_out.write_text(json.dumps(vectors(), indent=2), encoding='utf-8')
        return 0
    gui = args.gui or (default_gui and not args.headless) or bool(args.verify_ui)
    args.no_sql = args.no_sql or (not gui and not args.sql)
    if not gui:
        if not 0 < args.seconds <= 86400:
            p.error('Headless duration must be 0 < seconds <= 86400')
        from .headless import run
        return run(args)
    try:
        from .app import run_gui
    except ImportError as exc:
        p.error(f'Desktop dependencies unavailable ({exc.name}). Install atomverse-point-engine[gui]. The headless API remains available.')
    return run_gui(args)


def desktop_main(argv=None):
    return main(argv, default_gui=True)
