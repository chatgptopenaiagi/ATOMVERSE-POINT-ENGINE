import json
import math
import os
from pathlib import Path
import subprocess
import sys
import pytest

from atomverse_point import Kernel, History, replay
from atomverse_point.cli import main
from atomverse_point.conformance import vectors


def test_public_api_and_conformance():
    result = vectors()
    assert result['absolute_relative']['position'] == (-1., 1., -1.)
    assert result['line']['position'] == pytest.approx((3., -2., 1.), abs=1e-10)
    assert math.isclose(result['oscillator']['oscillator_value'], 3*math.sin(2*math.pi*2*73/240+.25), abs_tol=1e-10)
    assert result == vectors()


def test_cli_never_imports_gui_for_core(tmp_path):
    code = "import sys; from atomverse_point.cli import main; main(['--conformance-out', sys.argv[1]]); assert not any(x.startswith(('PySide6','psutil','pyodbc')) for x in sys.modules)"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path/'vectors.json')],env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path/'vectors.json').read_text())['line']['position'] == pytest.approx([3,-2,1], abs=1e-10)


def test_headless_cli_creates_replayable_history(tmp_path):
    commands = tmp_path/'commands.json'
    commands.write_text(json.dumps([{'action':'teleport','position':[-5,2,3]}, {'action':'oscillator','enabled':True,'frequency':2,'amplitude':3}]))
    assert main(['--seconds','.15','--data-dir',str(tmp_path),'--command-file',str(commands)]) == 0
    result = json.loads((tmp_path/'headless-result.json').read_text())
    assert result['state']['position'] == [-5.,2.,3.]
    assert not result['renderer_created'] and result['sql_status'] == 'disabled'
    assert replay(tmp_path/'history.db',result['history']['session_id'])[-1]['frequency'] == 2


def test_invalid_cli_command_is_rejected(tmp_path):
    commands = tmp_path/'commands.json'
    commands.write_text('[{"action":"execute","shell":"unsafe"}]')
    assert main(['--seconds','.1','--data-dir',str(tmp_path),'--command-file',str(commands)]) == 1
    result = json.loads((tmp_path/'headless-result.json').read_text())
    assert result['errors'] and result['state']['position'] == [0.,0.,0.]
