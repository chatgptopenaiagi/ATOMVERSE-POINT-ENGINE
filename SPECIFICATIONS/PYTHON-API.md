# Python API and command line

Install the wheel with Python 3.11 or newer. Core execution needs only the standard library, including SQLite. The release evidence identifies the Python versions actually tested; optional GUI availability depends on PySide6's supported Python/platform combinations.

```python
from atomverse_point import Kernel, History, replay

kernel = Kernel(sim_hz=240)
kernel.submit({"action": "teleport", "position": [-2, 1, 3]})
kernel.submit({"action": "oscillator", "enabled": True,
               "frequency": 2, "amplitude": 3, "phase": 0.25})
kernel.submit({"action": "trajectory", "trajectory": {
    "kind": "helix", "duration": 2, "amplitude": 2,
    "frequency": 0.5, "pitch": 0.4}})
history = History("experiment/history.db", kernel.state.point_id,
                  {"sim_hz": 240})
try:
    for event in kernel.drain_events():
        history.record(event)
    history.sample(kernel.state.snapshot())
    for _ in range(480):
        kernel.step()
        for event in kernel.drain_events():
            history.record(event)
        history.sample(kernel.state.snapshot())
finally:
    history.close()
print(kernel.state.snapshot())
recorded_states = replay(history.path, history.session_id)
```

`Kernel.submit` is synchronous on its owning thread. Use `Runtime.submit` for the independent fixed-step worker; never mutate its kernel from another thread. Accepted commands pass the same strict validator on every platform. History is a bounded asynchronous journal: close it to commit queued records. `replay` returns recorded states; `exact_reexecution` separately reexecutes accepted operations. An installed package does not require a renderer to do any of this.

```powershell
atomverse-point --version
atomverse-point --seconds 2 --data-dir .\experiment --command-file .\commands.json
python -m atomverse_point --seconds 1 --data-dir .\another-experiment
atomverse-point --gui
```

The CLI defaults to headless execution with SQL disabled. `--sql` opts into replication; install the `sql` extra and configure a valid connection first. `--no-sql` is also accepted. The legacy `atomverse-point-engine` entry point keeps desktop launch behavior. `--gui` requires `pip install "atomverse-point-engine[gui]"` (or the downloaded wheel path with `[gui]`).

Optional AI uses `atomverse_point.ai.propose` against an existing loopback Ollama endpoint. Call it from a worker or executor, show the returned structured proposal to the operator, then explicitly submit a reviewed command. It does not execute commands itself. The base package includes this HTTP client without a model download or GUI dependency. Network/model failures raise errors without altering the kernel.

Units, limits, the schema-2 snapshot format and human vision remain unchanged. The wheel is a Python distribution, not a standalone executable. Uninstalling it removes its code and CLI, while user histories remain in their selected data directories.
