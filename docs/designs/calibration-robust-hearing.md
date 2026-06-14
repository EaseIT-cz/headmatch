# Design: Calibration-robust hearing measurement (0.8.3)

Status: **draft for review.** Targets 0.8.3. Some parts are well-grounded in the
literature; others are explicitly flagged as needing their own focused review
before implementation (same discipline as
`docs/designs/measurement-resolution-eq.md`).

## Problem

The 0.8.2 hearing test is pure-tone threshold audiometry (Modified
Hughson-Westlake) mapped to EQ via the half-gain rule. The half-gain rule — and
every clinical prescriptive formula (NAL-NL2, DSL, CAM2) — is defined on
**absolute hearing loss in dB HL relative to a normal reference**. HeadMatch has
no SPL/RETSPL calibration: it maps thresholds through an *assumed*
`dBFS ≈ comfortable volume` reference. So the absolute "loss" is **volume-knob
dependent**, not ear-dependent:

- A real user test (2026-06-14) measured every frequency 15–20 dB "better than
  normal" because the playback volume was high enough to hear the test floor →
  zero compensation, a flat EQ. The data also never converged (all frequencies
  cap-terminated, < 3 ascending runs) yet were marked `determined: true`.

The literature is explicit: uncalibrated audiogram (threshold) measures are
sensitive to missing calibration and noise, whereas **supra-threshold tests can
be constructed to be invariant against missing calibration**
([medRxiv 2024.06.25.24309468](https://www.medrxiv.org/content/10.1101/2024.06.25.24309468v1.full));
and even validated app audiometry has only 60–77% test-retest agreement within
5 dB ([Saliba et al., AJA 2022](https://pubs.asha.org/doi/10.1044/2022_AJA-21-00191)).

A single *absolute* reference is the wrong tool here. But measuring the **relative
response shape at one fixed listening level** is calibration-invariant (the absolute
system gain cancels) and is the appropriate goal for a music-EQ tool. This reframes the
objective from *clinical hearing-loss prescription* to **perceptual response calibration
at the listening volume** — see Part B. (Self-referencing is not a valid *clinical*
prescription, but for perceptual calibration, referencing to the user's own fixed level
is the standard, correct approach.)

## Goals

1. Produce a hearing-derived EQ that is **robust to the absolute volume setting**.
2. Stay grounded in peer-reviewed methodology; flag every approximation.
3. Keep — but make honest — the existing pure-tone path.

## Part A — Engine guards (faithful to Hughson-Westlake; do first)

These bring the *existing* pure-tone path back into conformance and make any
measurement trustworthy. Low-risk, no new science.

1. **Honest `determined`.** A `FrequencyThreshold` is `determined: true` only when
   the staircase truly converged (≥3 ascending runs with the 2-of-last-3 rule).
   Cap-terminated / non-converged results become `determined: false` (carried as
   low-confidence, **excluded from EQ**). The engine exposes a `converged` flag
   distinct from `done`.
2. **Flooring detection.** If a frequency is still heard at `MIN_LEVEL_DBFS`
   (the floor), flag it `floored`. Many floored frequencies ⇒ surface "volume
   too high — lower it and retest" instead of recording fake thresholds.
3. **Volume/level pre-check.** A short calibration step before the test: play a
   reference tone and a near-floor tone so the user sets a level where the
   quietest tones are *near* inaudible. Also an L/R channel check ("which ear?")
   to confirm per-ear routing reaches the hardware.

## Part B — Relative response calibration at a fixed reference (primary)

**Goal (reframed).** Instead of clinical hearing-loss prescription (which needs
absolute dB HL we cannot calibrate), measure the listener's **perceived response
shape at the single volume they actually listen at**, and EQ it toward flat (or a
target). Music plays at one master volume, so this matches real use; and because
everything is measured *relative to one fixed reference*, the absolute system gain
cancels (calibration-invariant). It also naturally includes the **headphone's own
tuning**, since tones are measured *through* the headphone.

**Method — keeps the familiar "I hear it" flow. No loudness matching, no per-frequency
volume knob.**

1. The user sets the **master volume once** so a 1 kHz reference tone is comfortable;
   that reference level is fixed for the whole test.
2. For each frequency, the app varies only the **tone level digitally** (master
   untouched), using the same Hughson-Westlake staircase + "I hear it" interaction
   (with Part A's guards), to find the audibility threshold **relative to the
   reference** — `rel_thr(f)`, in dB below the 1 kHz reference. Only the *framing*
   changes vs today: relative to the user's own reference, not an absolute population
   value.
3. Repeat per ear — per-ear EQ falls out naturally.

**Isolating the deviation (required, or we over-boost the extremes).** A normal ear is
*naturally* far less sensitive at the frequency extremes, so flattening the raw
`rel_thr(f)` would wrongly boost deep bass / high treble for everyone. Subtract the
**normal relative reference shape** (normal threshold-in-quiet / equal-loudness contour,
referenced to 1 kHz). This is a *relative* reference and needs no absolute calibration:

```
dev(f) = [ rel_thr_user(f) − rel_thr_user(1 kHz) ] − normal_rel_shape(f)
```

`dev(f) > 0` ⇒ the user is less sensitive than normal at f (through this headphone) ⇒
boost. `dev(f)` then feeds the measured-resolution EQ (bands at the measured
frequencies, LSQ gains, 127-point GraphicEQ).

**What this measures, honestly.** `dev(f)` captures **hearing + this headphone**
combined — which is exactly what reaches the listener's perception, so for a
hearing-only music EQ that is the right quantity. It is **not** a clinical audiogram and
must not be presented as one. To separate headphone from hearing, use the
mic-measurement workflow.

> ⚠ **Needs a short focused review before coding** (smaller than a full study). Two
> things to ground and cite: (a) the source/shape of `normal_rel_shape(f)` — ISO 389-8
> reference-equivalent thresholds vs an ISO 226 equal-loudness contour at a comfortable
> phon level; (b) how aggressively to map `dev(f)` → gain — full correction vs a
> fraction — given listeners prefer softer high-frequency correction (PMID 23357807)
> and self-test thresholds carry ±5 dB spread. Reuse the EQ design doc's 12 dB cap and
> noise deadband.

## Part C — Keep the absolute (clinical-style) interpretation (guarded, optional)

Part B and the legacy path share the *same* measurement (the Hughson-Westlake
"I hear it" staircase). They differ only in interpretation: Part B reads it
**relatively** (perceptual calibration, calibration-invariant — the **default**),
while the legacy path reads it **absolutely** (half-gain vs the population reference)
to produce a clinical-style audiogram + EQ. Retain the absolute interpretation as an
optional output for users who have a calibrated level, with Part A's guards applied so
it never emits non-converged/floored thresholds as if determined.

## Part D — Hearing test in basic mode

Add `hearing-test` to `BASIC_NAV_ITEMS` (currently advanced-only). Small,
parked from earlier; do once Parts A/B stabilise.

## Compensation model interaction

Part B's `dev(f)` per frequency flows into the same **measured-resolution EQ** path
from `docs/designs/measurement-resolution-eq.md` (bands at the measured frequencies,
interaction-aware least-squares gains, standard 127-point GraphicEQ). Only the *source*
of the per-frequency gains changes; the realisation is unchanged. Per-ear EQ (vs the
current L/R average) becomes natural here since the relative-threshold test is per ear —
worth doing in 0.8.3.

## Open questions for the focused review (Part B)

1. `normal_rel_shape(f)` source: ISO 389-8 reference-equivalent threshold shape vs an
   ISO 226 equal-loudness contour at a comfortable phon level (and which level).
2. `dev(f)` → gain aggressiveness: full correction vs a fraction; interaction with the
   12 dB cap and noise deadband; listeners prefer softer HF correction (PMID 23357807).
3. Test-retest reliability of self-administered *relative* thresholds vs the absolute
   ±5 dB figure.
4. Frequency set: keep the 7 audiometric points, or add a few for shape resolution?

## Sequencing

1. Part A (guards) — independent, high value, no new science.
2. Short focused review for `normal_rel_shape` + `dev`→gain mapping → update this doc.
3. Part B (relative-threshold measurement at a fixed reference + grounded mapping +
   per-ear EQ).
4. Part C wiring + Part D basic-nav.

## References

- ISO 389-8 / ISO 226 — reference-equivalent thresholds and equal-loudness contours
  (source for the normal relative reference shape).
- medRxiv 2024.06.25.24309468 — relative / supra-threshold measures robust to missing
  calibration.
- Saliba et al., AJA 2022 (doi:10.1044/2022_AJA-21-00191) — app audiometry
  validity and ±5 dB test-retest.
- Carhart & Jerger 1959 — Modified Hughson-Westlake (the retained pure-tone path).
- PMID 23357807 — listeners prefer softer HF prescription (informs Part B aggressiveness).
- `docs/designs/measurement-resolution-eq.md` — the shared EQ realisation.
