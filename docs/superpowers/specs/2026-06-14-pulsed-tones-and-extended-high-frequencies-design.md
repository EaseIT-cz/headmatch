# Pulsed-Tone Stimulus + Opt-in Extended High Frequencies — Design

**Date:** 2026-06-14
**Status:** Approved design, pending spec review
**Scope:** one spec, one PR

Two independent additions to the hearing test, both touching the tone stimulus
and frequency protocol:

1. **Pulsed tone train** — replace the single continuous tone with a rapid
   sequence of 2–4 pulses (random count) so the subject is confident they truly
   heard the tone. Standards-based; does not skew thresholds.
2. **Opt-in extended high frequencies (EHF)** — 10, 12.5, 16 kHz, off by default,
   with a coloration warning. When enabled they shape the EQ (desired), using
   verified ISO 389-5:2006 reference values.

All changes centre on `headmatch/hearing_test.py`, with runner changes in the CLI
(`run_cli_hearing_test`) and GUI (`gui/views/hearing_test.py`) and minor wiring in
`cli.py` and `pipeline.py`.

---

## Part 1 — Pulsed Tone Train

### 1.1 Rationale and safety

Pulsed pure tones are the ASHA-recommended audiometric stimulus: equal or
marginally **more** sensitive than a steady tone, and easier to detect for
listeners with tinnitus (a steady tone can blend into the tinnitus). The only
threshold-skew risk is pulses shorter than ~200 ms, where temporal integration
elevates the threshold — so each pulse stays **≥ 200 ms**.

Switching continuous → pulsed may shift all thresholds by ~0–2 dB (slightly more
sensitive). This is uniform, so it **cancels in the relative path** (every
frequency is referenced to the ear's own 1 kHz) and sits well within the absolute
path's 10 dB deadband — negligible effect on the resulting EQ. The normal-shape
and normal-reference tables therefore need no re-anchoring.

### 1.2 Stimulus generation

New constants:

```python
PULSE_DURATION_S = 0.22     # per-pulse duration (≥ 0.20 s to avoid threshold elevation)
PULSE_GAP_S      = 0.15     # silence between pulses
PULSE_COUNT_MIN  = 2
PULSE_COUNT_MAX  = 4
```

New function `generate_tone_train(freq_hz, level_dbfs, sample_rate, ear, rng)`:

- Draws a pulse count uniformly in `[PULSE_COUNT_MIN, PULSE_COUNT_MAX]` from the
  injected `rng` (deterministic in tests).
- Builds **one** stereo `(N, 2)` buffer: each pulse is a `PULSE_DURATION_S` sine
  at `level_dbfs` with the existing 30 ms raised-cosine onset/offset ramps,
  pulses separated by `PULSE_GAP_S` of silence, routed to the chosen ear exactly
  like `generate_tone` (left / right / both).
- Max train length = `4 × 0.22 + 3 × 0.15 = 1.33 s`, comfortably inside
  `RESPONSE_WINDOW_S = 2.0 s`.

`generate_tone` is retained for the single comfort/channel-check tones in the GUI
(it builds a fixed-`TONE_DURATION_S` tone); `generate_tone_train` builds its
shorter pulses directly rather than calling `generate_tone`. Only the **staircase
presentations** switch to `generate_tone_train`.

### 1.3 Runner integration

Both runners already do: play a buffer via `backend.play_tone(...)`, then open one
`RESPONSE_WINDOW_S` response window. The change is a **drop-in buffer swap** — the
staircase presentation plays a tone train instead of a single tone. Therefore:

- One pulse train = one presentation = one response. `ThresholdEngine` is
  **unchanged** (pure detection logic).
- The random pulse *count* provides the "I heard 3 beeps" confidence cue without
  altering detection semantics.
- Silent catch trials remain silent (`generate_silence`, unchanged); jittered
  pre-tone timing still precedes each presentation.
- The CLI and GUI runners both take the existing injected `rng`, which now also
  drives the pulse count.

---

## Part 2 — Opt-in Extended High Frequencies (10, 12.5, 16 kHz)

### 2.1 Frequency set and opt-in

```python
EXTENDED_HF_FREQUENCIES = (10000, 12500, 16000)   # opt-in only
```

- **Off by default.** Opt-in via CLI `--extended-hf` and a GUI checkbox on the
  intro screen.
- Coloration note shown wherever it's enabled:
  > "Frequencies above 8 kHz are dominated by your headphone's response and how it
  > sits on your head. Enabling them shapes the 'air' band / coloration, not just
  > your hearing."
- The runner builds its frequency list/order from
  `TEST_FREQUENCIES (+ EXTENDED_HF_FREQUENCIES if opted in)`. EHF tones are tested
  **after 8 kHz**, before the 1 kHz re-check and the low-frequency descent, e.g.:
  `1000, 2000, 3000, 4000, 6000, 8000, 10000, 12500, 16000, 1000, 500, 250`.

### 2.2 Reference values (verified against ISO 389-5:2006 Table 1, HDA 200)

Using the **IEC 60318-1 coupler** column (same coupler as our ISO 389-8 values;
its 8 kHz entry is 17.5 dB, matching ISO 389-8 — confirming the column choice):

| Hz | RETSPL (dB SPL) | − RETSPL(1000)=5.5 → relative shape |
|------|------|------|
| 10000 | 22.0 | **+16.5** |
| 12500 | 27.5 | **+22.0** |
| 16000 | 53.0 | **+47.5** |

- `NORMAL_RELATIVE_SHAPE_DB` gains: `10000: 16.5, 12500: 22.0, 16000: 47.5`
  (exact RETSPL − 5.5).
- `NORMAL_HEARING_REFERENCE` (the softened absolute dBFS curve) gains EHF entries
  anchored at 8 kHz (−42.0) plus the **raw** ISO 389-5 RETSPL increments over
  8 kHz (RETSPL(8000)=17.5):
  - `10000: −42.0 + (22.0 − 17.5) = −37.5`
  - `12500: −42.0 + (27.5 − 17.5) = −32.0`
  - `16000: −42.0 + (53.0 − 17.5) = −6.5`

  (EHF uses the un-softened increment because the steep, physically-real EHF rise
  shouldn't be flattened; the absolute path's 10 dB deadband absorbs the rest.)

### 2.3 Both compensation paths

`compute_compensation_points` currently iterates the hardcoded `TEST_FREQUENCIES`,
which would silently drop EHF. Change it to iterate the **profile's actually
determined frequencies** (`sorted(set(profile.left) | set(profile.right))`). This
makes EHF flow through:

- the **absolute** path (`compute_compensation_curve` → `fit --with-hearing-compensation`
  and the GUI preview), and
- the **relative** path (`compute_relative_compensation` → equipment-free `fit`),
  which already iterates the profile's keys.

Result: when EHF is enabled and determined, it shapes the EQ in **both** workflows
(the desired coloration shaping). Untested frequencies are naturally excluded
because they aren't in the profile.

### 2.4 PTA4 / WHO unchanged

`PTA4_FREQS` stays `(500, 1000, 2000, 4000)`; EHF never enters the PTA4 average or
WHO grade.

### 2.5 Limitation (documented)

A normal 16 kHz threshold (−6.5 dBFS reference) sits near the test's max level
(`MAX_LEVEL_DBFS = −5.0`). Many listeners will not bracket 16 kHz at a safe
volume; those points return **undetermined** and are skipped (existing behaviour).
This is expected for EHF and is noted in the coloration message.

---

## 3. Files touched

- `headmatch/hearing_test.py` — pulse constants + `generate_tone_train`; EHF
  constants + reference-table entries; `compute_compensation_points` iterates the
  profile's frequencies; runner uses the tone train and an `extended_hf` flag to
  build the frequency order.
- `headmatch/gui/views/hearing_test.py` — pulse train in the event loop; EHF
  opt-in checkbox + coloration note on the intro screen; EHF in the order when
  enabled.
- `headmatch/cli.py` — `--extended-hf` flag wired to `run_cli_hearing_test`;
  coloration note in output.
- `headmatch/pipeline.py` — no signature change expected (both paths already take
  the profile); verify EHF points propagate.
- `docs/designs/hearing-personalization.md` — document pulsed stimulus and the
  opt-in EHF protocol + ISO 389-5 references.
- `tests/` — see below.

---

## 4. Testing

**Pulsed tones (`tests/test_hearing_pulsed.py`, new):**
- `generate_tone_train` returns a stereo buffer; pulse count within
  `[MIN, MAX]` for a seeded rng; each pulse ≥ `PULSE_DURATION_S`; total length <
  `RESPONSE_WINDOW_S`; ear routing (left silences right, etc.); ramps applied
  (no full-amplitude discontinuity at pulse edges).
- A simulated listener still converges through the runner with tone trains
  (staircase unaffected).

**EHF (`tests/test_hearing_ehf.py`, new):**
- Default run: frequency set/order unchanged (no EHF).
- Opt-in: order contains exactly 10/12.5/16 kHz, placed after 8 kHz.
- Reference tables contain the verified EHF entries.
- `compute_compensation_points` includes EHF when determined in the profile and
  excludes frequencies absent from the profile.
- PTA4/WHO ignore EHF.
- Undetermined EHF point is skipped without error.

**Regression:** existing hearing tests stay green; full suite + `mypy headmatch`
clean.

---

## 5. References (all public)

- ASHA — *Guidelines for Manual Pure-Tone Threshold Audiometry* (pulsed-tone
  stimulus recommendation).
- ISO 389-5:2006 — *Acoustics — Reference zero for the calibration of audiometric
  equipment — Part 5: RETSPL for pure tones in the frequency range 8 kHz to
  16 kHz* (HDA 200, IEC 60318-1 coupler column: 10k=22.0, 12.5k=27.5, 16k=53.0 dB).
- ISO 389-8:2004 — RETSPL for HDA 200, 125 Hz–8 kHz (existing reference; 8 kHz
  cross-checks at 17.5 dB).
- Carhart & Jerger (1959) — Modified Hughson-Westlake (existing).
