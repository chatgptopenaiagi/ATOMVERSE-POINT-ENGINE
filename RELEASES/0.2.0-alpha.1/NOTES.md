Version 0.2.0-alpha.1 adds the two-world model to the existing single-point engine: computation continues independently of visualization, and the same entity can be projected as a sphere, wave, spiral, signal or data.

**Release classification: PARTIAL. Core executable acceptance: PASS.** Dedicated SQL database provisioning remains unavailable because the current SQL login lacks CREATE DATABASE permission. Verified local SQLite history remains active. This is not a database engine failure.

- 74 automated tests, 24 packaged GUI checks and 9 real Qwen command cases pass.
- Oscillator, information state, create/delete/restore, optional hardware modulation and closed-window/headless execution are implemented.
- The reproduced ODBC buffer-binding failure is fixed. Real SQL recovery restores 1,003 records, and retry creates no duplicates.
- Local recording was measured through 2,000 Hz in bounded tests with no dropped samples. Temporary SQL throughput is not represented as permanent-storage throughput.
- Qwen is the existing 27.3B Q4_K_M model. Final inference requests eight GPU layers with compact summaries; all executable proposals remain reviewable.
- The previous 0.1.0-alpha.1 executable is preserved locally. No unrelated application, existing model installation or database was modified.

Download the Windows x64 ZIP, extract the complete folder, and launch `ATOMVERSE-POINT-ENGINE.exe`. Keep `_internal` beside it. SHA-256 checksums and final acceptance evidence are attached. The executable is unsigned experimental software.

Snapshot restore reconstructs recorded values and pauses; use command reexecution for original analytic trajectory operations. The engine is soft real time and has bounded queues/retention. Abrupt process or OS failure can lose the uncommitted journal tail. No physical atomic behavior or subjective consciousness is claimed.
