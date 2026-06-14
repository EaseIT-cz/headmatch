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

Self-referencing thresholds to the user's own best frequency was considered and
**rejected**: it is not a literature-backed prescription method. The
calibration-robust path the literature actually supports is a **supra-threshold
(loudness) measure**.

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

## Part B — Supra-threshold, calibration-invariant measurement (primary)

**Method: cross-frequency equal-loudness matching (method of adjustment).**

- Present a reference tone (1 kHz) at a fixed comfortable level.
- For each test frequency, the user adjusts that tone's level until it sounds
  **equally loud** as the reference.
- The level offset needed, `match(f)` (dB relative to 1 kHz), is a **within-
  session, fixed-volume relative comparison**, so the absolute system gain
  cancels — it is calibration-invariant by construction.

**Grounding:** equal-loudness matching and equal-loudness contours are
established psychoacoustics (ISO 226; Fletcher–Munson), and supra-threshold
measures are the calibration-robust option the smartphone-audiometry literature
recommends (medRxiv 2024, above).

**Isolating the hearing component (the subtle part).** `match(f)` reflects three
things mixed together: the headphone's own FR, the user's hearing, and the
*natural* equal-loudness contour shape (a normal ear is itself less sensitive at
the extremes). We must not "correct" the natural contour — music is already
mastered for normal ears. So the hearing deviation is:

```
hearing_dev(f) = match_user(f) − match_normal(f)
```

where `match_normal(f)` is the normal-listener equal-loudness offset at the same
phon level (from ISO 226). Both terms are relative-to-1 kHz, so `hearing_dev`
stays calibration-invariant. The EQ boosts where the user needed *more* level
than normal to match (reduced sensitivity).

> ⚠ **Needs its own literature review before implementation.** Mapping a
> supra-threshold/loudness deviation to EQ gain is *loudness restoration*, not the
> half-gain threshold rule. There is a body of work on loudness-based fitting
> (LGOB, IHAFF/Contour, categorical loudness scaling) with its own gain rules and
> caveats. Before coding Part B's prescription, run a focused research pass (like
> the EQ rework) to choose and cite the supra→gain mapping, the right phon level,
> and how aggressively to apply `hearing_dev`. Do **not** reuse the half-gain
> fraction blindly here.

**UX caveat.** Method-of-adjustment loudness matching is harder than "I hear it"
threshold detection (two-tone alternation + a level slider/buttons). The flow
must make the comparison easy and allow re-matching.

## Part C — Keep the pure-tone path (guarded)

Retain pure-tone threshold audiometry as a secondary/clinical-style option with
Part A's guards. It remains useful where the user *can* establish a sensible
level, and it is the cited Hughson-Westlake method. The supra-threshold loudness
test becomes the **default** because it is calibration-robust.

## Part D — Hearing test in basic mode

Add `hearing-test` to `BASIC_NAV_ITEMS` (currently advanced-only). Small,
parked from earlier; do once Parts A/B stabilise.

## Compensation model interaction

Whatever Part B produces (`hearing_dev` per frequency) flows into the same
**measured-resolution EQ** path from `docs/designs/measurement-resolution-eq.md`
(bands at the measured frequencies, interaction-aware least-squares gains,
standard 127-point GraphicEQ). Only the *source* of the per-frequency gains
changes; the realisation is unchanged. Per-ear EQ (vs the current L/R average)
becomes natural here since loudness matching is per ear — worth doing in 0.8.3.

## Open questions for the focused review (Part B)

1. Supra-threshold → gain mapping: which loudness-restoration rule, and how does
   it compare to half-gain? Is partial restoration preferred (as listeners
   preferred softer NAL-NL2 over louder CAM2, PMID 23357807)?
2. Reference phon level for matching, and `match_normal(f)` source (ISO 226 vs a
   simpler anchor).
3. Test-retest reliability of self-administered loudness matching vs the ±5 dB
   threshold figure.
4. Minimum frequency set for matching (the 7 audiometric points, or fewer?).

## Sequencing

1. Part A (guards) — independent, high value, no new science.
2. Focused literature review for Part B's prescription mapping → update this doc.
3. Part B (equal-loudness matching + grounded mapping + per-ear EQ).
4. Part C wiring + Part D basic-nav.

## References

- ISO 226 — equal-loudness-level contours.
- medRxiv 2024.06.25.24309468 — supra-threshold measures robust to missing
  calibration.
- Saliba et al., AJA 2022 (doi:10.1044/2022_AJA-21-00191) — app audiometry
  validity and ±5 dB test-retest.
- Carhart & Jerger 1959 — Modified Hughson-Westlake (the retained pure-tone path).
- PMID 23357807 — listeners prefer softer HF prescription (informs Part B aggressiveness).
- `docs/designs/measurement-resolution-eq.md` — the shared EQ realisation.
