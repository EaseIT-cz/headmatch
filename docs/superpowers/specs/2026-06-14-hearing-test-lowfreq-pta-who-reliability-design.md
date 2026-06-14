# Hearing Test: 250 Hz, PTA4/WHO Summary, and False-Positive Handling — Design

**Date:** 2026-06-14
**Status:** Approved design, pending spec review

## 1. Overview

Three independent, standards-based additions to the hearing test. All use
public-domain / published methods only; nothing here reuses any proprietary or
patented technique.

| # | Addition | Purpose |
|---|----------|---------|
| A | Add 250 Hz to the test protocol | Low-frequency hearing info + fuller audiogram + better low-end EQ coverage |
| B | PTA4 average + WHO-2021 hearing grade | Legible, user-facing summary of the result |
| C | Catch trials + timing jitter | Suppress and *measure* false-positive ("phantom") responses |

**Explicitly out of scope** (decided during brainstorming):
- **No extension above 8 kHz.** Above ~8 kHz, headphone FR + seat/seal variance
  dominate the measurement and our public reference data (ISO 389-8 HDA200) stops
  at 8 kHz; extending would equalize headphone coloration rather than hearing.
- Forced-choice / ear-localization paradigm (corrupts near-threshold readings).
- RETSPL per-device calibration; per-ear PEQ; NAL-NL2 prescription.

All changes are centered on `headmatch/hearing_test.py`, with runner changes in
both `run_cli_hearing_test` (CLI) and `gui/views/hearing_test.py` (GUI event loop).

---

## 2. Part A — Add 250 Hz

Pure-parameter change. Touches four module constants plus tests; no engine logic
changes — 250 Hz flows through the existing per-frequency staircase loop.

```python
TEST_FREQUENCIES = (250, 500, 1000, 2000, 3000, 4000, 6000, 8000)

# ISO 8253-1 order: 1 kHz first, ascend, re-verify 1 kHz, descend to lowest last.
TEST_ORDER = (1000, 2000, 3000, 4000, 6000, 8000, 1000, 500, 250)
```

Two new reference entries are required:

```python
NORMAL_HEARING_REFERENCE[250]   # provisional ≈ -45.0  dBFS
NORMAL_RELATIVE_SHAPE_DB[250]   # provisional ≈ +11.0  dB relative to 1 kHz
```

> **✓ VERIFIED against ISO 389-8:2004 Table 1 (HDA 200):**
> - `NORMAL_RELATIVE_SHAPE_DB[250] = 12.5` — **exact**. ISO Table 1 gives
>   RETSPL(250) = 18.0 dB and RETSPL(1000) = 5.5 dB, so the relative-to-1 kHz
>   shape is 18.0 − 5.5 = 12.5 dB. (The 500/2000/3000/4000/8000 entries also
>   match the standard exactly.)
> - `NORMAL_HEARING_REFERENCE[250] = −45.0` — this table is a *softened* dBFS
>   heuristic (not raw RETSPL), so there is no single "correct" ISO value. −45.0
>   is ~3 dB less sensitive than 500 Hz, matching the curve's own LF compression
>   (to within ~0.5 dB). It is **not** used by PTA4 (250 Hz is excluded), so it
>   only affects the legacy absolute-compensation path.
>
> **Incidental fix (pre-existing bug, corrected here):** `NORMAL_RELATIVE_SHAPE_DB[6000]`
> was 8.7, but ISO 389-8 Table 1 lists RETSPL(6000) = 17.0 → 11.5 dB (the old code
> comment wrongly claimed 6 kHz was absent from the table). Corrected to 11.5. The
> higher normal-shape value means a gentle HF slope at 6 kHz is correctly treated as
> mostly the ear's natural rise, yielding slightly less 6 kHz boost; one relative-
> compensation test fixture was re-calibrated to a genuine moderate deviation.

**Decoupling note:** 250 Hz is *not* used by PTA4 (which is 500/1k/2k/4k), so
Parts A and B stay independent. 250 Hz participates in the EQ compensation curve
through the existing `compute_compensation_points` / `compute_relative_compensation`
paths with no special-casing.

---

## 3. Part B — PTA4 + WHO Grade Summary

### 3.1 Estimated hearing level

Reuses the existing "loss" computation (already in `compute_compensation_points`):

```
est_HL(ear, f) = threshold_dbfs(ear, f) − NORMAL_HEARING_REFERENCE[f]
                  # positive = worse than the normal reference
```

This is an *estimate* of dB HL, not calibrated clinical dB HL (we operate in
relative dBFS). All reporting must carry this caveat.

### 3.2 PTA4 and better-ear grade

```
PTA4(ear) = mean( est_HL(ear, f) for f in {500, 1000, 2000, 4000} )
```

- Require **≥ 3 of the 4** frequencies *determined* for that ear; otherwise
  `PTA4(ear) = None`.
- Better-ear PTA = `min(PTA4_left, PTA4_right)` (lower dB = better hearing).
- If both ears are `None`, no grade is produced.

WHO 2021 better-ear grade bands (`WHO_GRADE_BANDS` constant):

| Better-ear PTA (dB) | Grade label |
|---------------------|-------------|
| < 20  | No impairment |
| 20 – <35 | Mild |
| 35 – <50 | Moderate |
| 50 – <65 | Moderately severe |
| 65 – <80 | Severe |
| 80 – <95 | Profound |
| ≥ 95 | Complete |

Negative est_HL (better than reference) is left as-is (grades to "No impairment");
no clamping.

### 3.3 API and surfacing

New pure function in `hearing_test.py`:

```python
def compute_hearing_summary(profile: HearingProfile) -> dict:
    # returns:
    # {
    #   "pta4_left_db": float | None,
    #   "pta4_right_db": float | None,
    #   "better_ear_pta_db": float | None,
    #   "who_grade": str | None,           # None when insufficient data
    #   "estimated": True,                  # always True — uncalibrated
    # }
```

Surfaced in:
- `hearing_fit_report.json` — new `"hearing_summary"` block.
- GUI results screen (`_show_results`) — PTA + grade line.

Both surfaces show a clear disclaimer:
> *Estimated from an uncalibrated self-test — not a medical diagnosis. See an
> audiologist for clinical assessment.*

---

## 4. Part C — Catch Trials + Jitter

Targets the expectation/criterion bias behind "phantom" responses, using the
standard clinical countermeasure (silent catch trials) plus de-rhythming (jitter).
Single-button UX is unchanged.

### 4.1 New constants

```python
CATCH_TRIAL_PROB        = 0.2    # chance of inserting a catch before a real tone
MAX_CATCH_TRIALS_PER_FREQ = 4    # bound runtime
FP_RATE_WARN            = 0.34   # > 1/3 false positives -> unreliable
JITTER_MIN_S            = 0.5
JITTER_MAX_S            = 2.0
```

### 4.2 Shared, testable policy helper

Because the CLI runner and the GUI event loop are separate implementations, the
*policy* is extracted into small pure helpers in `hearing_test.py` so both call
the same logic and tests can drive it deterministically:

```python
def should_insert_catch(rng: random.Random, n_inserted_this_freq: int) -> bool:
    return (n_inserted_this_freq < MAX_CATCH_TRIALS_PER_FREQ
            and rng.random() < CATCH_TRIAL_PROB)

def jittered_delay(rng: random.Random) -> float:
    return rng.uniform(JITTER_MIN_S, JITTER_MAX_S)

def is_unreliable(catch_count: int, false_positive_count: int) -> bool:
    return catch_count >= 3 and (false_positive_count / catch_count) > FP_RATE_WARN
```

Both runners accept an optional injected `rng` (default a fresh `random.Random()`)
for deterministic tests.

A truly-silent buffer is needed for catch trials (a small helper or
`np.zeros((n, 2))` matching tone duration).

### 4.3 Mechanics

- **Catch trial:** before a real presentation, if `should_insert_catch(...)`,
  play a silent buffer for the same duration and open the same response window.
  A response = false positive. **A catch trial does NOT call
  `engine.record_response()`** — the `ThresholdEngine` staircase stays pure.
  Per ear, accumulate `catch_count` and `false_positive_count`.
- **Jitter:** replace the fixed pre-tone gap with `jittered_delay(rng)`. (In the
  CLI runner this is a pre-tone sleep; in the GUI it is a pre-tone timer delay.)
- **Reliability flag:** after each ear, if `is_unreliable(...)`, mark that ear
  unreliable, warn the user, and suggest a retest. **Data is not auto-discarded.**

### 4.4 Data model changes

`HearingProfile` gains optional, backward-compatible fields:

```python
@dataclass
class HearingProfile:
    ...
    catch_stats: dict[str, dict[str, int]] | None = None
    # e.g. {"left": {"catch": 6, "false_positive": 1}, "right": {...}}
    unreliable_ears: list[str] | None = None    # subset of ["left", "right"]
```

`to_dict` / `from_dict` updated with defaults so **old saved profiles still load**
(missing fields → `None` / `[]`).

---

## 5. Testing

New / extended tests (extending the existing `tests/test_hearing_*.py` suite):

- **`compute_hearing_summary`**: PTA math; better-ear selection; each WHO band
  boundary (19/20/34/35/.../94/95); `< 3 of 4` determined → `None`; both ears
  missing → no grade.
- **250 Hz**: constants present and mutually consistent; simulated listener
  converges at 250 Hz; 250 excluded from PTA4 but present in compensation points.
- **Catch / jitter helpers** (seeded `random.Random`): catch insertion respects
  prob and per-freq cap; false-positive accounting; `is_unreliable` trips exactly
  at the boundary; `jittered_delay` within `[MIN, MAX]`; engine staircase result
  unaffected by interleaved catch trials.
- **Profile round-trip** with new fields, plus **back-compat load** of a profile
  JSON lacking `catch_stats` / `unreliable_ears`.

---

## 6. Files touched

- `headmatch/hearing_test.py` — constants, `compute_hearing_summary`,
  `WHO_GRADE_BANDS`, catch/jitter helpers, `HearingProfile` fields + serialisation,
  `run_cli_hearing_test` runner.
- `headmatch/gui/views/hearing_test.py` — catch/jitter in the event loop;
  PTA/WHO + reliability warning on the results screen.
- Report writer (hearing fit report JSON) — `hearing_summary` block.
- `docs/designs/hearing-personalization.md` — update frequency set, add PTA/WHO and
  reliability sections.
- `tests/test_hearing_*.py` — new coverage above.

---

## 7. References (all public / public-domain)

- ISO 8253-1 — pure-tone audiometry method & test order.
- ISO 7029:2017 — age-related normal threshold statistics (250 Hz reference).
- ISO 389-8 — HDA200 RETSPL (relative shape; 250 Hz–8 kHz).
- WHO (2021) — *World Report on Hearing*, grades of hearing loss (better-ear PTA).
- Carhart & Jerger (1959) — Modified Hughson-Westlake (already implemented).
- Standard clinical practice — silent/catch trials for false-positive control.
