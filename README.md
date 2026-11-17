# ⚛️ ATOMVERSE POINT ENGINE

**One computational entity. Two worlds. Computation before perception.**

Version `0.2.0-alpha.1` extends the verified single-point foundation with a dimensionless oscillator, bounded information state, entity lifecycle, optional hardware modulation and independent perceptual views. The existing XYZ trajectories, native controls, recorded replay and local Qwen proposal workflow remain intact.

**Mission status: PARTIAL.** The native engine works with local durable history. SQL Server batching and real disconnect/retry behavior are verified using isolated temporary tables, but the dedicated persistent database cannot be provisioned by the current SQL login. This is a permission limitation, not a SQL engine failure. Permanent-storage throughput is not inferred from temporary-table measurements. Final build results are in [Mission 002 acceptance](EVIDENCE/MISSION-002-FINAL-ACCEPTANCE.json).

## Run the Windows application

Extract the complete portable release folder and launch `ATOMVERSE-POINT-ENGINE.exe`. Keep `_internal` beside the executable. No Python installation is required for the packaged application. The executable is an unsigned experimental Windows x64 build.

- **Point:** teleport or translate XYZ, radius, RGBA, intensity, wall behavior, pause/resume/stop/reset.
- **Flow:** line, circle, spiral, helix, validated mathematical expressions or explicit coordinates; velocity and acceleration.
- **Frequency:** amplitude, frequency, phase, information state and optional measured-hardware mapping.
- **Memory:** committed-event status, recorded sessions, replay, restore, create and delete.
- **AI:** local endpoint/model, reviewable structured proposals, bounded historical queries and labeled explanations.

Use the representation selector for sphere, wave, spiral, signal or data. Changing it never changes the mathematical state. Drag the 3D viewport to orbit; use the wheel to zoom. “Keep mathematical engine running” leaves the engine behind a system-tray icon when the window closes. The tray menu restores the visualization or stops the engine.

```powershell
.\ATOMVERSE-POINT-ENGINE.exe --sim-hz 240 --record-hz 120 --render-hz 60
.\ATOMVERSE-POINT-ENGINE.exe --headless --seconds 10 --no-sql --data-dir .\experiment --command-file .\commands.json
```

Example command file:

```json
[
  {"action":"oscillator","enabled":true,"amplitude":3,"frequency":2,"phase":0},
  {"action":"trajectory","trajectory":{"kind":"helix","duration":5,"amplitude":2,"frequency":0.2,"pitch":0.4}}
]
```

The local journal defaults to `%LOCALAPPDATA%\ATOMVERSE-POINT-ENGINE\history.db`. Keep one running application per data directory. Recorded history is distinct from the current mathematical state and from AI interpretation. Samples are bounded; gaps are counted. Abrupt process/OS failure can lose the uncommitted queue tail. The payload budget is 256 MiB plus a 16 MiB critical reserve, with additional SQLite/index/WAL overhead. Archive old data directories and start a new one when capacity is reached; the program never silently deletes history.

## Optional integrations

SQL Server: run `scripts/setup-sql.ps1` under an appropriately authorized SQL account. It creates only `ATOMVERSE_POINT_ENGINE` and applies additive migrations. Grant the runtime login only the necessary access to that dedicated database. By default the application uses local Windows authentication and Microsoft ODBC Driver 18. A private `ATOMVERSE_SQL_CONNECTION` environment variable can override the connection; never commit it. Default local encryption trusts the local server certificate; use a verified certificate for remote deployment. Local recording continues when SQL is unavailable.

Qwen: point the AI tab at an existing loopback Ollama server. The tested model is **27.3B**, not exactly 30B. The final Mission 002 configuration requests eight GPU layers, four CPU threads and a 2,048-token context for varied commands and awareness summaries; the measured offload uses about 3 GB VRAM. Set GPU layers to zero for CPU-only operation. The initial repeated-command benchmark favored CPU, but the broader workload exposed much slower CPU prompt processing. Inference is optional, asynchronous and reviewable. No model downloads or unrestricted model actions occur.

## Build and verify from source

Reuse a compatible existing Python environment where possible. Development was verified with Python 3.14.9, PySide6 6.11.0, pyodbc 5.3.0, psutil 7.2.2, pytest 9.1.1 and PyInstaller 6.22.3. Dependencies are declared in `pyproject.toml`.

```powershell
$python = 'path\to\verified\python.exe'
& $python -m pytest -q
.\scripts\run.ps1 -Python $python --no-sql
.\scripts\build.ps1 -Python $python
# The build writes a new timestamped candidate directory and preserves old builds.
```

Each candidate can run `--verify-ui <evidence-directory>` to exercise real native controls. `--verify-ai` additionally requires a real local model. See the scripts for actual SQL recovery, recording, native C++/CUDA and inference probes. Public evidence omits personal paths, credentials, raw inventories, histories and weights.

Read the [original human vision](CONCEPT/ORIGINAL-HUMAN-VISION.md), [two-world principle](CONCEPT/TWO-WORLDS-PRINCIPLE.md), [architecture](ARCHITECTURE.md), [oscillator definitions](ARCHITECTURE/ENERGY-FREQUENCY-KERNEL.md), [projection](ARCHITECTURE/PERCEPTUAL-PROJECTION.md), [AI awareness](ARCHITECTURE/AI-AWARENESS.md) and [roadmap](ROADMAP.md). The sphere is a computational representation, not a physical atom. Multi-entity worlds remain future work.
