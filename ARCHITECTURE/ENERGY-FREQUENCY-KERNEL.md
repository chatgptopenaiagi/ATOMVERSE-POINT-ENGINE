# Energy and frequency: defined quantities

The implemented oscillator is `s(t) = A sin(2πft + phase)`.

| Quantity | Definition and units | Classification |
|---|---|---|
| Amplitude A | Bounded dimensionless signal scale, 0–1,000,000 | Mathematical simulation |
| Frequency f | 0–1,000 cycles per simulation second | Mathematical simulation |
| Phase | Radians, bounded to ±1,000,000 | Mathematical simulation |
| Oscillator time | Elapsed enabled, unpaused simulation time in seconds | Mathematical simulation |
| Signal s(t) | Dimensionless computed oscillator value | Mathematical simulation |
| Hardware clocks | OS/driver-reported MHz | Observed telemetry |
| GPU board power | NVIDIA driver-reported watts when available | Observed telemetry; not process energy or independent wattmeter measurement |
| Effective amplitude | Result of an explicit mapping or manual amplitude | Derived computation |
| AI explanation | Model output referring to supplied state/evidence | AI interpretation |

Frequency, amplitude and phase are versioned, controllable and recorded. Pausing freezes oscillator time. Disabled oscillators retain their parameters and time but output zero. Changing parameters applies the formula immediately; phase continuity across arbitrary frequency changes is not inferred. Sampling above the Nyquist limit can alias in history or visual output; high mathematical frequency is not a promise that every cycle was captured. The current rates and capture policy are visible.

Optional modulation maps observed x to amplitude: `u = clamp((x-input_min)/(input_max-input_min), 0, 1)`, `A_effective = amplitude_min + u*(amplitude_max-amplitude_min)`. Configuration and inputs are inspectable and recorded. Interior values are invertible when the output range is nonzero; clamped endpoints and constant mappings have no unique inverse. Missing, stale or nonfinite telemetry never enters the signal as an unchecked number. Stale inputs fall back to manual amplitude. Disable restores manual amplitude immediately through the command queue.

No simulated value is called joules, atomic energy, consciousness, or a physical atomic transition frequency. Actual physical power observations are kept separate from the derived modulation. No claim is made that the artificial entity contains the GPU's energy.
