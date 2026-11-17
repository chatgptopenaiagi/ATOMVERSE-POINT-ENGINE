One authoritative mathematical kernel is now available in three verified distribution formats: Windows x64 EXE, a pure-Python wheel and an Android ARM64 APK. The original point, oscillator, trajectories, state schema and SQLite history remain shared.

**Mission 003 distribution acceptance: PASS.** Android was installed and executed as ARM64 on an API 37 emulator with ARM64 translation. A physical ARM64 device is **NOT TESTED**.

- Windows: standalone EXE and portable ZIP tested outside the source directory with Python removed from PATH. Both pass 25 native GUI checks, including AI-unavailable operation, replay and clean shutdown.
- Python: `atomverse_point_engine-0.3.0a1-py3-none-any.whl` installs and uninstalls in fresh Python 3.14 and 3.15 environments. Each runs all 78 tests; core imports and CLI work without Qt, ODBC or psutil. GUI/SQL/telemetry are optional extras.
- Android: signed, ARM64-only native application using the same Python kernel. Native controls, actual touch input, camera independence, oscillator, replay, SQLite integrity, background/resume and close/reopen restoration pass. No CUDA, SQL Server or Qwen model is needed.
- Eight mathematical scenarios agree across installed Python, packaged Windows and Android within absolute/relative tolerance `1e-10`.
- Three actual Qwen proposals pass. The installed model is 27.3B Q4_K_M. Real SQL disconnect recovery restores 1,003 records without duplication; dedicated database provisioning still requires an authorized SQL account.
- The previous release remains unchanged, and all 32 pre-existing local histories retain their original hashes and pass SQLite integrity checks.

Download the standalone Windows EXE directly, or extract the complete portable ZIP and retain `_internal` beside its executable. For Python, install the WHL using pip and run `atomverse-point --help`; a wheel requires Python. For Android, sideload the APK on a compatible ARM64 environment. Scroll the Android controls for transport and memory controls; backgrounding pauses the entity and a clean close checkpoints it.

Windows binaries are unsigned experimental builds. The APK is signed with a project-local key and is not a Play Store release. Android AI, SQL replication and hardware modulation are not included. Linux/macOS Python execution and other Android devices/API levels are NOT TESTED. Measurements describe bounded tests, not physical atomic behavior, consciousness or hard-real-time guarantees.

SHA-256 checksums and sanitized acceptance/package evidence accompany the artifacts. Failed intermediate verification checks and their repairs remain documented in the source repository.
