# Design: Measurement-resolution EQ generation

Status: adopted for the hearing-fit path (0.8.2). Retrofit across the other
fitting mechanisms is **pending a literature review** validating that the
approach (prescription rule, band placement, GraphicEQ frequency set) is optimal
— see "Open questions for the literature review" below.

## Principle

**The resolution of the generated EQ must match the resolution of the
measurement that produced it.** Do not manufacture frequency resolution the
data does not have.

The hearing test measures hearing thresholds at exactly seven audiometric
frequencies (ISO 8253-1: 500, 1000, 2000, 3000, 4000, 6000, 8000 Hz). The EQ has
seven degrees of freedom — no more. Cubic-spline-interpolating those seven points
onto a dense grid and then greedily fitting parametric bands (or exporting a
~5,000-point GraphicEQ) invents detail that was never measured, is slower, and —
in the GraphicEQ case — produced files large enough to crash downstream
consumers such as EasyEffects.

## Approach

Build the EQ **directly from the measured points**:

1. **Per-frequency gains.** Compute the target gain at each *measured* frequency
   (for the hearing fit: half-gain compensation `clamp((threshold − reference) ×
   0.5, 0, 12 dB)`, L/R averaged). This is `compute_compensation_points()` →
   `{freq_hz: gain_db}`.

2. **Parametric EQ.** One peaking filter per frequency that needs gain, placed
   *at* the measured frequency. Each filter's Q is derived from the band's
   spacing to its neighbours so adjacent bands meet near their −3 dB points
   instead of stacking:

   ```
   N      = mean octave distance to neighbouring measured frequencies
   Q(N)   = sqrt(2^N) / (2^N − 1)      # N=1 oct → 1.41 ; N=0.5 oct → 2.87
   ```

   `eq_bands_from_gain_points()`. When a smaller filter budget is requested, the
   largest-magnitude bands are kept (advanced mode can lower the budget; basic
   uses all measured points).

3. **GraphicEQ.** The measured points plus *hold-edge* anchors at 20 Hz and
   20 kHz (the nearest measured gain, so the host bounds its interpolation
   instead of ramping to zero). ~9 points total — `hearing_graphiceq_curve()`.

A modest 48-points/octave grid is still used, but **only** for prediction/
clipping metrics and for sampling a target curve at the measured frequencies —
never to manufacture EQ resolution.

### Why this is also "not random"

The legacy parametric fitter (`fit_peq`) is a deterministic greedy
residual-peak placer, not random. But running it over a spline-interpolated
dense grid still fabricates resolution. Placing bands at the measured/standard
frequencies is both deterministic *and* honest about the data.

## Retrofit plan (unify all fitting mechanisms)

The measurement-based fit (`fit_from_measurement` / `write_fit_artifacts`) and
the target-fit path should adopt the same principle:

- **Microphone measurement fit.** The analysis grid (~48 ppo) is a real
  measurement resolution, so its parametric fit is defensible — but the GraphicEQ
  export should be emitted on a **standard, bounded frequency set** (e.g. the ISO
  ⅓-octave preferred frequencies, or the AutoEq GraphicEQ standard set) rather
  than the full analysis grid, for consistent, host-safe files.
- **Shared GraphicEQ writer.** Centralise GraphicEQ point selection in one place
  with a single default frequency set and an advanced-mode override, so basic
  mode is identical everywhere and advanced mode exposes the same knob across
  hearing-fit, online measure, and offline fit.
- **Shared band-budget semantics.** `max_filters` / `FilterBudget` already unify
  the parametric count; extend the same default-in-basic / selectable-in-advanced
  pattern to GraphicEQ density.
- **Per-ear option.** The hearing test measures per ear but currently averages
  L/R into one curve. A future option can emit per-ear EQ from the per-ear
  thresholds.

## Open questions for the literature review

Before retrofitting, validate against peer-reviewed literature / standards:

1. Is the half-gain (Lybarger) rule the right prescription for a music-listening
   EQ from audiometric thresholds, or do NAL-NL2 / DSL v5 / CAM2 apply better?
2. Is placing parametric filters at the audiometric frequencies (Q from spacing)
   optimal vs optimisation-based placement for a sparse target?
3. What is the recommended standard GraphicEQ frequency set and point count?
4. What are the validity limits of uncalibrated (dBFS, no RETSPL) self-test
   audiometry as an EQ basis, and how should that bound the applied gain?

## References

- ISO 8253-1 — pure-tone audiometry test frequencies.
- ISO 266 — preferred (⅓-octave) frequencies for graphic-EQ band sets.
- Lybarger half-gain prescription rule (compensation gains).
- RBJ / standard peaking-filter Q ↔ octave-bandwidth relationship.

## Implementation pointers

- `headmatch/hearing_test.py`: `compute_compensation_points`,
  `eq_bands_from_gain_points`, `hearing_graphiceq_curve`,
  `_peaking_q_for_octave_bandwidth`.
- `headmatch/pipeline.py`: `fit_from_hearing_profile`, `run_hearing_fit`.
- Tests: `tests/test_hearing_test_bugfixes.py`.
