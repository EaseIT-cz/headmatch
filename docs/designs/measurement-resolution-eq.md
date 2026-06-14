# Design: Measurement-resolution EQ generation

Status: **adopted project-wide** (0.8.2). Grounded in a literature review (see
"Evidence" below); applies to the hearing-fit and measurement-fit paths.

## Principle

**The resolution and aggressiveness of the generated EQ must match the
resolution and *reliability* of the measurement that produced it.** Do not
manufacture frequency resolution the data lacks, and do not turn measurement
noise into EQ.

The hearing test measures thresholds at seven audiometric frequencies (ISO
8253-1: 500, 1000, 2000, 3000, 4000, 6000, 8000 Hz) — seven degrees of freedom,
each with ~5 dB+ test-retest spread. The EQ must reflect that.

## Approach

1. **Per-frequency gains with a noise deadband.** Compute the half-gain
   compensation at each measured frequency, `gain = clamp((threshold −
   reference) × 0.5, 0, 12 dB)`, L/R averaged — but **ignore losses below a
   ~10 dB deadband** (`HEARING_DEADBAND_DB`), which are within self-test noise
   and where the half-gain rule over-prescribes. `compute_compensation_points()`.

2. **Interaction-aware parametric realization.** One peaking filter per measured
   frequency (Q from inter-band octave spacing, `Q = sqrt(2^N)/(2^N − 1)` as an
   approximation of the RBJ octave↔Q relation). Band **gains are solved by
   least squares against an interaction matrix** so the realised chain hits the
   target points (overlapping bands sum) — not by assigning each band its raw
   point gain. `peq.solve_band_gains_lsq()`, `eq_bands_from_gain_points()`.
   Verified: realised response lands within ~0.3 dB of target at every measured
   frequency.

3. **Unified standard GraphicEQ grid.** Every GraphicEQ export (hearing-fit AND
   measurement-fit) renders the fitted PEQ chain onto the **AutoEq 127-point log
   grid** (`signals.standard_graphic_eq_grid()`, step 1.0563 from 20 Hz). This is
   the de-facto density standard, loads comfortably in Equalizer APO/EasyEffects,
   and replaced the ~5,103-point grid that crashed EasyEffects.

A modest 48-points/octave grid is still used for prediction/clipping metrics and
target sampling — never to manufacture EQ resolution.

## What was retrofitted

- **Hearing-fit** (`fit_from_hearing_profile`, `run_hearing_fit`): deadband +
  least-squares band gains + standard-grid GraphicEQ.
- **Measurement-fit** (`pipeline_artifacts.write_fit_artifacts`): GraphicEQ moved
  from the raw analysis grid to the standard 127-point grid. The parametric
  fitter (`fit_peq`, greedy residual placement) operates at true measurement
  resolution and is unchanged — placing bands at measured resolution does not
  violate the principle.
- **Shared utilities:** `signals.standard_graphic_eq_grid`,
  `peq.solve_band_gains_lsq`.

## Evidence (literature review)

Prescription rule (Q1):
- Half-gain (Lybarger) is an empirically validated first-order rule for
  sensorineural loss (~500 fitted clients) — Schwartz/Larson, *A Reexamination
  of the One-Half Gain Rule*, Ear & Hearing 1980 (PMID 7409361).
- It **over-prescribes for mild loss** (same source) → motivates the deadband.
- Modern formulas (NAL-NL2) are model-based, compressive optimizations, not a
  fixed fraction — Keidser et al., *Trends in Amplification* 2011,
  doi:10.1177/1084713812468511.
- Listeners **prefer the softer prescription** and cut aggressive HF gain by
  ~4 dB; gain is reduced for inexperienced users — Moore et al., PMID 23357807;
  doi:10.1177/1084713812465494 → keep the 0.5 fraction + 12 dB cap conservative.

Band placement / Q (Q2):
- Fixed standard-frequency bands + weighted least squares reconstruct an
  arbitrary target to <0.81 dB; band interaction must be modelled via an
  interaction matrix — Välimäki & Liski / Rämö et al., MDPI Appl. Sci. 2020
  10(4):1222; Aalto "Graphic EQ design with symmetric biquad filters".
- RBJ peaking realization `A = 10^(dBgain/40)` and the octave↔Q relation —
  webaudio Audio-EQ-Cookbook. AutoEq uses fixed Q (√2 octave, 4.318 for 31-band).

GraphicEQ grid (Q3):
- Equalizer APO GraphicEQ accepts an arbitrary point list (no documented max),
  interpolated linearly in log-frequency — SourceForge APO config reference. The
  EasyEffects crash was the point *count*, not the format.
- AutoEq's 127-point grid (step 1.0563) is the de-facto density standard —
  github.com/jaakkopasanen/AutoEq. Band sets follow ANSI S1.11-2004 / ISO 266.

Validity of uncalibrated self-audiometry (Q4):
- App audiometry can approximate clinical thresholds (no significant difference
  0.5–4 kHz), **but** test-retest within 5 dB is only 60–77% per frequency, and
  uncalibrated audiograms are sensitive to calibration/noise — Saliba et al.,
  AJA 2022, doi:10.1044/2022_AJA-21-00191; medRxiv 2024.06.25.24309468 →
  motivates the deadband and conservative, capped gains.

## Possible future work

- Taper the gain fraction at mild loss (Libby ⅓-gain style) rather than a hard
  deadband knee.
- Per-ear EQ from the per-ear thresholds (currently L/R averaged).
- Optional ISO-266 ⅓-octave GraphicEQ export alongside the AutoEq grid.

## Implementation pointers

- `headmatch/hearing_test.py`: `compute_compensation_points`,
  `eq_bands_from_gain_points`, `_peaking_q_for_octave_bandwidth`,
  `HEARING_DEADBAND_DB`.
- `headmatch/peq.py`: `solve_band_gains_lsq`.
- `headmatch/signals.py`: `standard_graphic_eq_grid`.
- `headmatch/pipeline.py`, `headmatch/pipeline_artifacts.py`: GraphicEQ export.
- Tests: `tests/test_hearing_test_bugfixes.py`, `tests/test_e2e_fitting.py`.
