# Mission 001 specification and traceability

The [human vision](../CONCEPT/ORIGINAL-HUMAN-VISION.md) governs this project. All positions use a shared right-handed XYZ coordinate system in dimensionless simulation units. A Python binary64 position is authoritative; GPU pixels, camera transforms, persisted samples and AI interpretations are separate representations.

| Requested stage | Implementation / evidence | Limit |
|---|---|---|
| 001 Workstation discovery | Hardware/software JSON, native compiler probes, CPU/GPU benchmark, Qwen and SQL reports | Private paths and inventories stay in ignored `.local` |
| 002 Three-dimensional space | Absolute teleport, relative displacement, velocity, trajectories, direct native controls, simulation-time scheduling, grid and independent orbit camera | Coordinates bounded to ±1e9; rendering precision is lower than binary64 state precision |
| 003 Sphere geometry | One point ID; radius, RGBA, intensity, solid/wireframe/transparent/luminous/center representations | Luminous means unshaded color, not a physical light source |
| 004 Projection engine | CREATED, SCHEDULED, ACTIVE, PAUSED, COMPLETED, CANCELLED, FAILED events, UUID command IDs | Schedule uses simulation time; wall-clock scheduling is deferred |
| 005 Flow engine | Line, circle, spiral, helix, bounded AST custom expressions, explicit polyline, manual velocity and acceleration | Trajectory duration and frequency have finite limits; custom coordinate derivatives use centered numerical differences |
| 006 Material rules | Infinite plane, sphere-expanded swept boundary; pass, stop, reflect, slide, custom restitution [0,1] | Idealized kinematic interaction; not physical atomic or material simulation |
| 007 Spatial memory | Bounded queue, SQLite WAL journal, asynchronous batched SQL replica, ordered event IDs, UTC nanoseconds, monotonic nanoseconds and ticks | Dedicated SQL database requires a sufficiently privileged SQL login; never substitute temporary-table tests for persistent deployment |
| 008 AI awareness | Optional local Ollama Qwen proposal → strict validator → visible review → deterministic execution | No OS actions. General historical explanation/planning interfaces are future work |
| 009 Qwen optimization | Actual local 27.3B GGUF Q4_K_M model; CPU and eight-layer GPU measurements | No 30B model was found in the inspected locations; no new model downloaded |
| 010 Acceleration | Scalar CPU math, actual OpenGL GPU renderer; CUDA, PyTorch and cuDNN bounded tests | No trivial single-point CUDA offload; future batch acceleration remains optional |
| 011 Native control | Windows Qt desktop, Point / Flow / Memory / AI, telemetry, instant direct controls | No browser or inference required for control |
| 012 Time / frequency | Independent launch options for simulation, capture and rendering; amplitude, phase and path frequency | Soft real time; delays slow simulation explicitly rather than silently skipping ticks |
| 013 First line / spiral | Single-point line, helix and trajectory trail; recorded polyline | Independent connected multi-point entities intentionally deferred, as permitted by Mission 001 |
| 014 Architecture | Pure kernel, simulation worker, immutable snapshots, GUI, journal worker, SQL worker, AI worker | One primary point per engine session |
| 015 Verification | Automated tests, actual native GUI automation, packaged executable, failure/recovery and numerical evidence | Evidence states actual, controlled failure, unsupported and unavailable distinctly |
| 016 Public repository | Sanitized source, documentation, scripts, evidence | No credentials, private inventories, histories or weights |
| 017 Windows executable | Portable x64 folder with `ATOMVERSE-POINT-ENGINE.exe` and replaceable runtime libraries | Unsigned alpha; keep the complete folder together |

## Coordinate and motion contract

Position, velocity and acceleration are finite triples bounded to ±1e9. Radius is 0.001–1e6. RGBA is [0,1] per channel. Invalid command schemas are rejected before enqueue; state-dependent failures produce FAILED without mutating the existing motion. Translation is an instantaneous displacement; neither translation nor teleport pretends to traverse intermediate positions. Use a line trajectory for continuous travel to a destination.

For constant acceleration: p(t+dt)=p(t)+v(t)dt+0.5a dt² and v(t+dt)=v(t)+a dt. The kernel uses fixed dt=1/simulation_hz. A trajectory's local clock advances only while moving. Circular and helical motion start continuously at the current position using a phase-relative offset: x=x0+a(cos(phase+2πft)−cos(phase)), y=y0+a(sin(phase+2πft)−sin(phase)); helix z=z0+pitch*t. Spiral radius is a+growth*t. Custom expressions are displacement functions normalized by f(t)−f(0). Polylines traverse the current position then each listed absolute vertex, with equal time per segment.

Paths end with stop or continue along the final tangent. At a collision, a path hands over to velocity motion (or stops) and records that change. The collision sweep tests the straight chord of a simulation step; accuracy for strongly curved or accelerated paths depends on step size. Teleports intentionally bypass swept collision tests. A moving sphere initially intersecting the plane is depenetrated to its nearest side. The rendered wall patch illustrates an infinite plane.

## Time and lifecycle

Ticks and event sequence numbers establish order. UTC is for historical correlation and may be adjusted by the OS; it is not an ordering clock. `timestamp_ns` is state-change UTC, while every sample also has capture UTC and monotonic time. Pausing freezes simulation time and motion. A future scheduled command cannot unpause a frozen simulation clock; resume directly. Stopped points still advance the simulation clock so future schedules can activate. Reset returns to the original position and cancels pending motions without changing point ID, appearance, tick or historical time.

Commands are first **queued**, then interpreted by the engine and journaled. The UI distinguishes committed journal counts from queued events. An abrupt OS/process failure may lose the bounded, not-yet-committed tail; this alpha does not claim synchronous command durability. Disk/queue failure is visible and stops the worker rather than pretending the experiment was fully recorded.

## Acceptance classification

The exact build outcome is in [FINAL-ACCEPTANCE.json](../EVIDENCE/FINAL-ACCEPTANCE.json). Mission status must remain PARTIAL while required deployed persistence or other required capabilities remain incomplete, even when the single-point executable passes its core acceptance suite. A functioning alpha release must state those limitations prominently.
