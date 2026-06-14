# Design: Calibration-robust hearing measurement (0.8.3)

Status: Targets 0.8.3. **Part A (guards) and Part D (basic-nav) shipped; the focused
literature review for Part B is complete (folded into Part B below); Part B + the A3
volume pre-check are the remaining implementation.**

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

### Focused review findings (resolved)

A focused literature review (adversarially verified; see References) answered the two
open questions. *Caveat:* the review's synthesis step hit a session limit, so these
conclusions rest on the fully-verified claims plus the prior EQ-design research pass.

**(a) `normal_rel_shape(f)` = ISO 389-8 RETSPL threshold shape, relative to 1 kHz.**
ISO 389-8 RETSPL values are *reference threshold-of-hearing levels* for circumaural
earphones (derived from otologically-normal listeners across five labs) — i.e. a
**threshold** reference, which is the right match for our threshold-based test. ISO 226
equal-loudness contours are *supra-threshold* and would only apply to a loudness measure,
so they are **not** used. The RETSPL contour has exactly the U-shape we must not
over-correct (≈ +30 dB @125 Hz, min ≈ 1–3 kHz, rising to +17.5 dB @8 kHz re 0 dB). Use
its value re 1 kHz at each test frequency:

```
normal_rel_shape(f) ≈ RETSPL(f) − RETSPL(1 kHz)   (ISO 389-8, HDA 200)
  500:+5.5  1k:0  2k:−1  3k:−3  4k:+4  6k:≈+7.5(interp)  8k:+12   dB
```

Caveat: RETSPL is earphone-specific and we measure uncalibrated through an arbitrary
headphone, so the residual `dev(f)` still folds in this headphone's deviation — exactly
the "hearing + headphone" quantity we acknowledged. (A claim that the transducer must be
"flat within 10–15 dB over 250 Hz–8 kHz" was **refuted** in review, so we impose no such
hard band limit.)

**(b) Map `dev(f)` → gain with a conservative fraction, a deadband, and a cap — and let
the user fine-tune.** Apply a **fraction** of `dev(f)` (the half-gain 0.5 is the
established, literature-backed fraction; preferred functional gain is ≈ half the
deviation), **deadband** small deviations (self-administered audiometry agrees within
5 dB only 60–77% of the time per frequency), and keep the **12 dB cap** from the EQ
design doc. High-frequency aggressiveness is **genuinely contested** in the literature —
some listeners trim prescribed HF gain by ~4 dB and prefer the softer prescription, yet
for mild sloping losses the higher-HF prescription is preferred, and preference depends
on input level. So we do **not** hard-code HF reduction beyond the cap; instead keep HF
gain moderate and **expose user adjustment of the proposed correction** (the comparison
studies all let listeners adjust). Steep HF loss correlates with preferring *less* HF
extension, which the cap + fraction already respect.

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

## Remaining questions (post-review)

1. Whether to expose the per-region user adjustment in the first 0.8.3 cut or a later
   iteration (the studies all let listeners adjust the proposed correction).
2. Exact interpolation of `normal_rel_shape` at 6 kHz (not in the ISO 389-8 HDA 200
   table); interpolate on log-frequency.

## Sequencing

1. ✅ Part A (guards) — honest `determined` + flooring detection (shipped).
2. ✅ Focused review for `normal_rel_shape` + `dev`→gain mapping (folded in above).
3. Part B (relative-threshold measurement at a fixed reference + ISO 389-8 normal-shape
   subtraction + fractional/capped/deadbanded mapping + per-ear EQ + user adjustment).
4. Part C wiring + ✅ Part D basic-nav (shipped) + A3 volume pre-check (with Part B).

## References

- **ISO 389-8:2004** — RETSPL (reference threshold-of-hearing levels) for circumaural
  earphones; the threshold-based normal reference shape used in (a). Verified threshold
  (not loudness) reference with the U-shaped contour.
- ISO 226 — equal-loudness contours (supra-threshold; *not* used for a threshold test).
- medRxiv 2024.06.25.24309468 — relative / supra-threshold measures robust to missing
  calibration.
- Saliba et al., AJA 2022 (doi:10.1044/2022_AJA-21-00191) — self-test audiometry agrees
  within 5 dB only 60–77% of the time per frequency (deadband rationale).
- Moore & Sęk 2013 (Ear & Hearing 34(1):83–95) and PMID 23357807 / doi:10.1177/
  1084713812465494 — CAM2 vs NAL-NL2: HF-gain preference is mixed and depends on loss
  slope and input level (informs "moderate HF + user-adjustable, not hard-coded").
- ResearchGate 5620852 — steep HF-loss slope correlates with preferring narrower
  bandwidth (less HF extension).
- Carhart & Jerger 1959 — Modified Hughson-Westlake (the retained pure-tone path).
- `docs/designs/measurement-resolution-eq.md` — the shared EQ realisation.
