# Technology selection after discovery

The workstation's existing Python 3.14, PySide6 6.11, pyodbc, psutil, pytest and PyInstaller installations were reused read-only. No new Python environment was created. Existing ATOMVERSE AI, COG and ARX installations were left unchanged. Godot's version command and the C++ toolchain were inspected, but a full generic engine was unnecessary for the first entity. Qt Quick 3D was absent from the existing Qt installation; native Qt OpenGL bindings were present and passed actual rendering tests.

| Choice | Reason and evidence |
|---|---|
| Python binary64 kernel | One point requires little computation; readable deterministic tests and strict interfaces matter more than a compiled loop at this scale |
| Qt native widgets + OpenGL | Existing working install; real NVIDIA rendering confirmed, orbit/zoom independent of point position |
| Existing PyInstaller | Builds a portable Windows x64 folder without modifying sibling projects |
| SQLite WAL plus SQL Server replica | Durable local replay survives SQL outages; network/database operations stay off the simulation/render paths |
| SQL Server 2022 via ODBC 18 | Real connectivity, transactions and batching measured; dedicated database provisioning denied for the current login |
| Optional Ollama / Qwen | Existing 27.3B Q4_K_M model, no weights downloaded; strict structured command proposal boundary |
| CPU default inference, 4 threads, 2,048 context | Repeated short command was approximately as fast as eight-layer offload while preserving VRAM for rendering |
| CPU scalar math; optional CUDA batches | A measured one-point CUDA transfer cost far exceeded scalar CPU arithmetic; larger resident tensor batches benefited from the GPU |

The installed model advertises `qwen35` architecture, 65 blocks, 27,320,697,856 parameters and a 262,144 model context limit. The engine tests use only 2,048 tokens. The 17.7 GB local blobs do not fit entirely in 6 GB VRAM. Eight requested offload layers used approximately 3.06 GB VRAM while the remainder stayed in host memory. Model runtime memory was approximately 18 GB. These are actual Ollama metadata/serving measurements, not estimates that a 30B model fits on the GPU.

The first inference test returned a schema-valid relative displacement for an absolute request. The final prompt explicitly distinguishes TO and BY; a new nonzero-position test then passed in CPU and hybrid modes. The original failed semantic result is retained as baseline evidence. One correct prompt does not validate arbitrary language control. Review remains mandatory in the application.

Measured results live in [CPU-GPU-PERFORMANCE.json](../EVIDENCE/CPU-GPU-PERFORMANCE.json), [QWEN-INFERENCE.json](../EVIDENCE/QWEN-INFERENCE.json), [SQL-THROUGHPUT.json](../EVIDENCE/SQL-THROUGHPUT.json), and [GUI-VERIFICATION.json](../EVIDENCE/GUI-VERIFICATION.json). Short probes are workload-specific observations, not thermal or indefinite sustained-capacity guarantees. The compute and recording benchmarks may run under ordinary workstation load; the evidence names that limitation.

Primary references: [Qt QOpenGLWidget](https://doc.qt.io/qtforpython-6/PySide6/QtOpenGLWidgets/QOpenGLWidget.html), [Qt licensing](https://doc.qt.io/qtforpython-6/licenses.html), [ODBC datetime support](https://learn.microsoft.com/en-us/sql/relational-databases/native-client-odbc-date-time/odbc-api-support-for-enhanced-date-and-time-features?view=sql-server-ver15), [pyodbc batch extensions](https://github.com/mkleehammer/pyodbc/wiki/Features-beyond-the-DB-API). Installed tool outputs, real inference and executable tests supply the operational evidence.

## Mission 002 refinement

The table above preserves the Mission 001 decision. The broader Mission 002 workload changes prompts and includes recent-state context. CPU prompt processing was much slower than repeated identical prompts, and the original large GUI context exceeded its 90-second request deadline. The final configuration uses three compact recent-event references, an action-specific JSON grammar, explicit action examples and eight GPU layers. The varied-command measurements support this combination; they do not isolate a pure GPU speedup from the simultaneous prompt/schema improvements. CPU-only operation remains selectable. Baseline failures and the final suite are both retained in evidence.
