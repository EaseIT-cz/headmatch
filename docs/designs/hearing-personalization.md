# Hearing Personalisation — Architecture and Scientific Basis

## 1. Overview

HeadMatch can personalise the EQ preset to a listener's individual hearing thresholds.
Two usage paths are supported:

| Path | Equipment required | Accuracy |
|------|--------------------|----------|
| **Hearing-only** (`headmatch hearing-fit`) | Headphones under test + quiet room | Moderate — assumes flat headphone FR |
| **Measurement + compensation** (`headmatch fit --with-hearing-compensation`) | Headphones + measurement microphone | High — real headphone FR plus personalisation |

The hearing test itself is identical in both paths.

---

## 2. Measurement Procedure

### 2.1 Modified Hughson-Westlake Pure-Tone Audiometry

The threshold engine in `headmatch/hearing_test.py` implements the
**Modified Hughson-Westlake procedure** (Carhart & Jerger, 1959 — public domain).

**Algorithm ("up-5 down-10"):**
1. Start at a comfortable listening level (−20 dBFS peak).
2. After a *heard* response: decrease level by 10 dB.
3. After a *missed* response: increase level by 5 dB (ascending run begins).
4. An ascending run closes when the listener responds while the level is ascending.
5. **Threshold declaration**: lowest level heard on ≥ 2 of the most recent 3 ascending runs.
6. **Minimum 3 ascending runs** required before a threshold can be declared.
7. **Maximum 8 ascending runs** (constant `MAX_ASCENDING_RUNS`): if exceeded, the most-frequently-heard level is used as a best estimate.

This procedure is a standard clinical method published in the public domain;
no proprietary algorithm is used.

**Reference:**
> Carhart, R., & Jerger, J. (1959). Preferred method for clinical determination of
> pure-tone thresholds. *Journal of Speech and Hearing Disorders*, 24(4), 330–345.

### 2.2 Frequency Set and Test Order

Frequencies follow **ISO 8253-1** (Pure tone audiometry — basic pure-tone
air and bone conduction threshold audiometry; public international standard):

- **Test frequencies**: 500, 1000, 2000, 3000, 4000, 6000, 8000 Hz
- **Test order**: 1000 → 2000 → 3000 → 4000 → 6000 → 8000 → 1000 → 500 Hz

The 1 kHz frequency is visited twice to provide an inter-run reliability check.
Both measurements are reconciled by using only the first visit in the threshold
table (the duplicate entry is skipped by the `processed_freqs` set in the runner).

### 2.3 Relative dBFS Levels (No RETSPL Calibration)

Clinical audiometry uses **dB HL** (Hearing Level), a calibrated absolute scale
referenced to the Reference Equivalent Threshold Sound Pressure Level (RETSPL),
which is transducer-specific. HeadMatch operates entirely in relative **dBFS**
(digital full-scale), which avoids device-specific calibration but requires that
the listener first sets a **consistent comfortable listening volume** before the test.

This volume setting anchors the whole test: a tone at −20 dBFS will be
approximately 30 dB above a normal-hearing listener's threshold at 1 kHz,
so the starting level (−20 dBFS) is perceptually familiar as "comfortable music."

The `NORMAL_HEARING_REFERENCE` dictionary records the expected threshold level
for a young adult (18–25 yrs) with normal hearing at a comfortable listening
volume. Values are derived from **ISO 7029:2017** median data (age-related
hearing threshold statistics for otologically normal persons) mapped to the
project's relative dBFS scale.

```python
NORMAL_HEARING_REFERENCE = {
    500:  -48.0,   # dBFS — expected threshold at 500 Hz
    1000: -50.0,
    2000: -50.0,
    3000: -49.0,
    4000: -47.0,
    6000: -44.0,
    8000: -42.0,
}
```

**Reference:**
> ISO 7029:2017. *Acoustics — Statistical distribution of hearing thresholds
> related to age and gender.* International Organization for Standardization.

---

## 3. Compensation Curve

### 3.1 Half-Gain Rule

The per-frequency EQ compensation gain is computed using the **half-gain rule**
(Lybarger, 1944 — public domain, predating all modern patents):

```
loss(f)  = measured_threshold(f)  −  NORMAL_HEARING_REFERENCE(f)
              [positive when threshold is worse than reference]

gain(f)  = clamp( loss(f) × 0.50,  0 dB,  12 dB )
```

The half-gain fraction (0.50) is the most widely cited rule-of-thumb for
initial hearing aid gain prescription. It produces a modest boost that
compensates for reduced sensitivity without over-amplifying in quiet
environments. The 12 dB maximum cap (`MAX_COMPENSATION_DB`) prevents
extreme boosts from unstable or outlying threshold estimates.

**References:**
> Lybarger, S. F. (1944). *Method of fitting hearing aids*. US Patent 2,360,181
> (now expired; the half-gain rule itself is in the public domain).
>
> Killion, M. C., & Fikret-Pasa, S. (1993). The 3 types of sensorineural hearing
> loss: loudness and intelligibility considerations. *The Hearing Journal*, 46(11),
> 31–36.

### 3.2 Bilateral Averaging

Left and right threshold measurements are averaged at each frequency before
computing the compensation gain:

```python
avg_threshold(f) = mean(left_threshold(f), right_threshold(f))
```

If one ear is undetermined, only the other ear's threshold is used.
This produces a single symmetric compensation curve applied equally to
both EQ channels. Listeners with very large L/R asymmetry (> 15 dB at
any frequency) receive a warning; their compensation may not be optimal
and an audiologist consultation is recommended.

### 3.3 Interpolation and Smoothing

Only 7 test frequencies are available. To produce a continuous compensation
curve on the analysis frequency grid:

1. **Cubic spline interpolation** on the log-frequency axis (`scipy.interpolate.CubicSpline`,
   not-a-knot boundary condition). Log-frequency spacing respects the logarithmic
   nature of auditory perception.
2. **1-octave Gaussian smoothing** via the existing `fractional_octave_smoothing()`
   function. This eliminates sharp EQ peaks that could arise from noisy threshold
   estimates at individual frequencies.
3. Gain values are clamped to [0, MAX_COMPENSATION_DB] after smoothing.

---

## 4. Pipeline Architecture

### 4.1 Measurement + Compensation (Full Path)

```
┌─────────────────────┐     ┌──────────────────┐
│  Headphone sweep    │     │  Hearing test     │
│  (microphone req.)  │     │  (ears only)      │
└─────────┬───────────┘     └────────┬──────────┘
          │ MeasurementResult        │ HearingProfile
          │ freqs_hz, L/R dB         │ thresholds per freq
          └───────────┬──────────────┘
                      │
              fit_from_measurement()
                      │
              resolved_target  =  base_target(f) + compensation(f)
              eq_target(f)     =  resolved_target(f) − measured_FR(f)
                      │
                  fit_peq()
                      │
              PEQ bands  →  EQ preset files
```

Key call site in `pipeline.py:fit_from_measurement()`:
```python
compensation = compute_compensation_curve(hearing_profile, result.freqs_hz)
left_eq_target = (resolved_target.left_values_db + compensation) - result.left_db
```

The compensation is folded into the target *before* the PEQ fitter runs.
This means the existing pipeline, analysis, confidence scoring, and artifact
writing are completely unchanged.

### 4.2 Hearing-Only Path (No Measurement Equipment)

```
┌─────────────┐
│  Hearing    │
│  test       │
└──────┬──────┘
       │ HearingProfile
       │
fit_from_hearing_profile()
       │
  freqs    = geometric_log_grid(20 Hz, 20 kHz, 512 points)
  flat     = 0 dB  (assumed headphone FR)
  target   = flat or user-supplied target CSV
  eq_target = target(f) + compensation(f)
       │
   fit_peq()
       │
run_hearing_fit()
       │
  equalizer_apo.txt
  camilladsp_full.yaml
  camilladsp_filters_only.yaml
  equalizer_apo_graphiceq.txt
  hearing_fit_report.json
  README.txt
```

Key function: `pipeline.py:fit_from_hearing_profile()` and `run_hearing_fit()`.

The flat headphone assumption means the EQ bands encode *only* the
compensation curve (plus any target deviation). This is suitable as a
starting point; it can be iteratively refined by re-running with a
real headphone measurement using `--with-hearing-compensation`.

---

## 5. Tone Playback

Test tones are pure sine waves with 30 ms raised-cosine onset and offset
ramps to eliminate clicks. Generated by `generate_tone()` in `hearing_test.py`:

```python
mono = np.sin(2.0 * np.pi * freq_hz * t)
ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_ramp) / n_ramp))
mono[:n_ramp] *= ramp
mono[-n_ramp:] *= ramp[::-1]
mono *= 10.0 ** (level_dbfs / 20.0)
```

Tones are played via `backend.play_tone(samples, sample_rate, device)` —
a thin method on both the PipeWire and PortAudio backends that plays
audio without any recording, leaving the existing `play_and_record` path
completely unaffected.

**Tone stimulus parameters (from CTA-2118 2023 guidance on minimum audible threshold testing):**
- Duration: 1.0 s
- Ramp: 30 ms raised cosine (onset + offset)
- Response window: 3.0 s from tone start
- Inter-tone interval: 0.8 s silence between responses

---

## 6. Data Model

```python
@dataclass
class FrequencyThreshold:
    freq_hz: int
    level_dbfs: float | None   # None when undetermined
    ascending_runs: int
    determined: bool

@dataclass
class HearingProfile:
    left: dict[int, FrequencyThreshold]
    right: dict[int, FrequencyThreshold]
    tested_at: str              # ISO 8601 timestamp
    asymmetric_freqs: list[int] # freqs where |L − R| > 15 dB
```

Profiles are serialised as JSON to `$XDG_CONFIG_HOME/headmatch/hearing_profile.json`
via `save_hearing_profile()` / `load_hearing_profile()`.

---

## 7. CLI Reference

```bash
# Run the hearing test interactively
headmatch hearing-test [--output-target DEVICE] [--sample-rate 48000] [--json]

# Run the hearing test and immediately generate an EQ preset (no microphone needed)
headmatch hearing-test --fit --out-dir ./hearing_eq

# Generate an EQ preset from a previously saved hearing profile
headmatch hearing-fit --out-dir ./hearing_eq [--target-csv harman.csv] [--max-filters 8]

# Apply hearing compensation during a headphone measurement fit
headmatch fit --recording recording.wav --out-dir ./fit --with-hearing-compensation
```

---

## 8. GUI Integration

**Hearing Test** appears in the advanced navigation sidebar.

After the test completes, the shell offers two choices:
1. **Generate EQ Preset Now** — calls `run_hearing_fit()` as a background task,
   assumes flat headphone FR, writes preset to `…/hearing_fit/`.
2. **Run a Measurement** — navigates to the Measure workflow. The saved
   `self.hearing_profile` is automatically passed to the online pipeline so
   compensation is applied during the next measurement fit.

---

## 9. Acceptance Criteria

| Test | Covered by |
|------|-----------|
| Threshold engine converges on simulated listener | `test_hearing_test.py::TestThresholdEngine` |
| Half-gain rule produces correct gain | `test_hearing_test.py::TestComputeCompensationCurve` |
| Gain capped at MAX_COMPENSATION_DB | `test_hearing_test.py::test_gain_capped_at_max` |
| No negative compensation | `test_hearing_test.py::test_no_negative_gain` |
| Profile round-trip serialisation | `test_hearing_test.py::TestHearingProfileSerialisation` |
| Compensation applied in pipeline | `test_hearing_compensation.py::TestHearingCompensationInPipeline` |
| Equipment-free fit writes all artifacts | `test_hearing_fit.py::TestRunHearingFit` |
| Normal hearing → near-flat EQ | `test_hearing_fit.py::test_normal_hearing_gives_small_boost` |
| 20 dB loss → positive boost | `test_hearing_fit.py::test_20dB_loss_produces_boost` |

---

## 10. Limitations and Future Extensions

| Limitation | Future work |
|------------|-------------|
| Flat headphone assumption in hearing-only path | Couple with a published HRTF/average-headphone FR |
| No RETSPL calibration | Per-transducer calibration table (device-specific dB HL offset) |
| Symmetric compensation applied to both channels | Per-ear PEQ bands when the pipeline supports per-channel fitting |
| Single comfort-volume anchor | Automated comfort calibration tone at session start |
| Half-gain rule is a rough heuristic | NAL-NL2 prescription (Dillon, 2012) when clinical data available |

---

## 11. References

1. Carhart, R., & Jerger, J. (1959). Preferred method for clinical determination of
   pure-tone thresholds. *Journal of Speech and Hearing Disorders*, 24(4), 330–345.

2. ISO 8253-1:2010. *Acoustics — Audiometric test methods — Part 1: Pure-tone air
   and bone conduction audiometry.* International Organization for Standardization.

3. Lybarger, S. F. (1944). *Method of fitting hearing aids.* US Patent 2,360,181
   (expired; half-gain rule in the public domain).

4. ISO 7029:2017. *Acoustics — Statistical distribution of hearing thresholds
   related to age and gender.* International Organization for Standardization.

5. Consumer Technology Association (2023). *CTA-2118: Method of Measurement for
   Minimum Audible Threshold of Personal Listening Devices.* CTA Standard.

6. Killion, M. C., & Fikret-Pasa, S. (1993). The 3 types of sensorineural hearing
   loss: loudness and intelligibility considerations. *The Hearing Journal*, 46(11), 31–36.

7. Dillon, H. (2012). *Hearing Aids* (2nd ed.). Boomerang Press / Thieme.
   [NAL-NL2 prescription background — not implemented; cited for future-work reference only.]
