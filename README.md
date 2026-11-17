# ⚛️ ATOMVERSE POINT ENGINE

**One computational entity. Two worlds. Computation before perception.**

Version `0.3.0-alpha.1` distributes one authoritative Python kernel as a standalone Windows application, an installable Python wheel and a native Android application. The existing XYZ trajectories, oscillator, entity lifecycle, desktop views, recorded replay and reviewed local Qwen workflow remain intact.

Mission 003 verification is recorded in [final acceptance](EVIDENCE/MISSION-003-FINAL-ACCEPTANCE.json). Windows and Python are mandatory release gates; Android is included only after actual ARM64 APK installation and execution. The previous [0.2.0-alpha.1 release](https://github.com/chatgptopenaiagi/ATOMVERSE-POINT-ENGINE/releases/tag/v0.2.0-alpha.1) remains unchanged.

| Distribution | Verified execution | Included capabilities | Limits |
| --- | --- | --- | --- |
| Windows EXE / portable ZIP | Windows 11 x64, native Qt/OpenGL | Full desktop engine, SQLite, optional SQL/Qwen/telemetry | Unsigned alpha; dedicated SQL database still requires authorized provisioning |
| Python `py3-none-any` wheel | Fresh CPython 3.14 and 3.15 environments on Windows x64 | Kernel, API, CLI, SQLite, optional AI client | Python 3.11+ required; GUI/SQL/telemetry extras are optional; Linux/macOS execution NOT TESTED |
| Android ARM64 APK | API 37 compatible emulator executing ARM64 via native translation | Same Python kernel, native touch controls, sphere/wave/spiral/signal/data, SQLite replay | Physical ARM64 device NOT TESTED; no SQL, CUDA, hardware modulation or local Qwen bundled |

The Android package declares API 24 as its minimum and targets API 36; only the execution environment above has been tested. A wheel's universal tag describes its pure-Python payload, not every optional adapter's platform support.

## Run the Windows application

Download `ATOMVERSE-POINT-ENGINE-0.3.0-alpha.1-windows-x64.exe` and launch it directly. It includes Python and its dependencies, extracting runtime files to a temporary directory on startup. Alternatively, extract the complete portable ZIP and launch its `ATOMVERSE-POINT-ENGINE.exe`, keeping `_internal` beside it. No manual Python installation is required. Both are unsigned experimental Windows x64 builds.

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

## Install the Python wheel

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install .\atomverse_point_engine-0.3.0a1-py3-none-any.whl
.\.venv\Scripts\atomverse-point --seconds 2 --data-dir .\experiment
.\.venv\Scripts\python -m atomverse_point --version
```

The base package needs no Qt, pyodbc, psutil, CUDA or AI model. Install the downloaded wheel with `[gui]`, `[sql]` or `[telemetry]` extras only when needed, for example `pip install ".\atomverse_point_engine-0.3.0a1-py3-none-any.whl[gui]"`. The `atomverse-point` CLI defaults to headless operation; add `--gui` for desktop controls. The legacy `atomverse-point-engine` command defaults to the GUI. See the [importable API and recording example](SPECIFICATIONS/PYTHON-API.md). Uninstall with `python -m pip uninstall atomverse-point-engine`; historical data is retained.

## Install the Android application

Install `ATOMVERSE-POINT-ENGINE-0.3.0-alpha.1-android-arm64.apk` on a compatible ARM64 Android environment. With developer tools: `adb install <apk-path>`. This is a project-signed sideloadable alpha, not a Play Store release.

The native interface offers XYZ teleport/relative movement, radius/color, oscillator frequency/amplitude/phase, line/helix movement and five perceptual views. Drag the scene to orbit the independent camera. Scroll the lower controls for pause, resume, replay, return to live state and save/close. SQLite history stays in app-private storage. Replay reads committed samples at recorded simulation times and never rewrites the live entity.

Backgrounding pauses and checkpoints the entity; returning resumes only if it was previously running. A clean close flushes history; reopening restores the saved entity values in a paused state. Android does not claim persistent background-service execution. Direct controls work offline without AI, SQL Server or NVIDIA hardware. Physical-device coverage and Android history export remain future work. See [Android feasibility and verification](RESEARCH/MISSION-003-ANDROID-FEASIBILITY.md).

## Build and verify from source

Reuse a compatible existing Python environment where possible. Development was verified with Python 3.14.9, PySide6 6.11.0, pyodbc 5.3.0, psutil 7.2.2, pytest 9.1.1 and PyInstaller 6.22.3. Dependencies are declared in `pyproject.toml`.

```powershell
$python = 'path\to\verified\python.exe'
& $python -m pytest -q
.\scripts\run.ps1 -Python $python --no-sql
.\scripts\build.ps1 -Python $python
.\scripts\build.ps1 -Python $python -Mode onefile
& $python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist\wheels
# The build writes a new timestamped candidate directory and preserves old builds.
```

Each candidate can run `--verify-ui <evidence-directory>` to exercise real native controls. `--verify-ai` additionally requires a real local model. See the scripts for actual SQL recovery, recording, native C++/CUDA and inference probes. Public evidence omits personal paths, credentials, raw inventories, histories and weights.

Android builds reuse an installed SDK/JDK/Gradle and a matching Python 3.14 runtime via `scripts/build-android.ps1`. Signing keys and machine paths stay under ignored local directories. Reproducing an update requires retaining the private signing key; it is never uploaded. The Java UI embeds `src/atomverse_point` through Chaquopy rather than rewriting the mathematics.

Read the [original human vision](CONCEPT/ORIGINAL-HUMAN-VISION.md), [two-world principle](CONCEPT/TWO-WORLDS-PRINCIPLE.md), [architecture](ARCHITECTURE.md), [oscillator definitions](ARCHITECTURE/ENERGY-FREQUENCY-KERNEL.md), [projection](ARCHITECTURE/PERCEPTUAL-PROJECTION.md), [AI awareness](ARCHITECTURE/AI-AWARENESS.md) and [roadmap](ROADMAP.md). The sphere is a computational representation, not a physical atom. Multi-entity worlds remain future work.
