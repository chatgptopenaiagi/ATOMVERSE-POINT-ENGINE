# Reverse perception architecture

The direction is hardware → execution → time → mathematical state → transformations → rules → recorded information → perceptual projection → human observation.

The existing spatial kernel remains the execution authority. Schema 2 adds oscillator state, information state and lifecycle without invalidating schema-1 histories. Position, radius and color are geometric facets. Frequency, phase, amplitude and information need no camera to exist. One active entity is enforced; deleting it records the transition and retains previous evidence. Creating a new entity assigns a new UUID. Restoration loads an inspected historical snapshot, preserves its identity and mathematical parameters, keeps the current event clock, and pauses before further execution. Hardware modulation is disabled on restore.

The native application supports sphere, wave, spiral, signal and data observers. View selection changes only GUI state. The headless path creates no renderer and records the same kernel state. A closed-window execution test verifies advancing ticks while no visualization is visible. A separate packaged headless test verifies operation without an application window.

System boundaries remain in [ARCHITECTURE.md](../ARCHITECTURE.md). Exact command reexecution is separate from sampled-history display. Command reexecution consumes accepted commands and recorded telemetry at their original ticks. Random creation identities are stored in the accepted command, so replay can preserve them. UTC and monotonic observation timestamps are not fabricated as deterministic outputs.

Snapshot restore reconstructs geometric, velocity, acceleration, oscillator and information values at a paused point on the current timeline. Resuming uses restored velocity/acceleration; it does not infer an unfinished analytic path from sampled positions. Use accepted-command reexecution to reproduce the original trajectory operations.

Future work: multiple independent entities, component arrays, inter-entity interaction, persistent background service, cross-process observers and large-population benchmarks. Version 0.2 does not claim these capabilities.
