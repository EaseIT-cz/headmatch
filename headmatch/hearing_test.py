"""Hearing threshold measurement and EQ compensation.

Implements the Modified Hughson-Westlake pure-tone threshold procedure
(Carhart & Jerger 1959, public domain) and the half-gain EQ compensation
rule (Lybarger 1944, public domain).

No proprietary algorithm or patented DSP method is used.
"""
from __future__ import annotations

import json
import math
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.interpolate import CubicSpline

from .paths import config_dir
from .signals import fractional_octave_smoothing


# ── Frequency protocol ────────────────────────────────────────────────────────

TEST_FREQUENCIES: tuple[int, ...] = (250, 500, 1000, 2000, 3000, 4000, 6000, 8000)

# ISO 8253-1 test order: start at 1 kHz, ascend, re-verify 1 kHz, descend to the
# lowest frequency last. The duplicate 1000 Hz entry allows reliability verification.
TEST_ORDER: tuple[int, ...] = (1000, 2000, 3000, 4000, 6000, 8000, 1000, 500, 250)

# Pure-tone average frequencies (WHO/clinical PTA4 — the standard four-frequency
# average). 250 Hz is measured for the audiogram and EQ but is NOT part of PTA4.
PTA4_FREQS: tuple[int, ...] = (500, 1000, 2000, 4000)

# Extended high frequencies (ISO 389-5 range), opt-in only. Above 8 kHz the
# headphone's response and fit dominate, so these shape the "air band"/coloration
# rather than pure hearing — enabled deliberately, never by default. Excluded
# from PTA4/WHO grading.
EXTENDED_HF_FREQUENCIES: tuple[int, ...] = (10000, 12500, 16000)


def build_test_order(extended_hf: bool = False) -> tuple[int, ...]:
    """Frequency presentation order. With ``extended_hf`` the opt-in EHF set is
    inserted right after 8 kHz (so the ascending sweep continues into the EHF
    band before the 1 kHz re-check and the low-frequency descent)."""
    if not extended_hf:
        return TEST_ORDER
    idx = TEST_ORDER.index(8000) + 1
    return TEST_ORDER[:idx] + EXTENDED_HF_FREQUENCIES + TEST_ORDER[idx:]

# ── Tone stimulus parameters ──────────────────────────────────────────────────

TONE_DURATION_S: float = 0.8
INTER_TONE_SILENCE_S: float = 0.5
RAMP_DURATION_S: float = 0.03       # 30 ms raised-cosine onset/offset

# Pulsed-tone stimulus: each staircase presentation is a rapid train of a random
# number of pulses (gives the listener confidence they truly heard the tone).
# Pulsed pure tones are the ASHA-recommended audiometric stimulus. Pulse duration
# stays >= 0.20 s so temporal integration does not elevate the threshold.
PULSE_DURATION_S: float = 0.22
PULSE_GAP_S: float = 0.15
PULSE_COUNT_MIN: int = 2
PULSE_COUNT_MAX: int = 4

# False-positive control: silent catch trials measure how often the listener
# responds when no tone is present, and jittered timing breaks the predictable
# rhythm that drives expectation-based "phantom" responses.
CATCH_TRIAL_PROB: float = 0.2           # chance of a silent catch before a real tone
MAX_CATCH_TRIALS_PER_FREQ: int = 4      # bound the extra presentations per frequency
FP_RATE_WARN: float = 0.34              # > 1/3 false positives -> ear flagged unreliable
JITTER_MIN_S: float = 0.5               # pre-tone silence is drawn uniformly from
JITTER_MAX_S: float = 2.0               # [JITTER_MIN_S, JITTER_MAX_S]

# ── Threshold engine parameters ───────────────────────────────────────────────

START_LEVEL_DBFS: float = -20.0     # first tone at comfortable level
MIN_LEVEL_DBFS: float = -70.0
MAX_LEVEL_DBFS: float = -5.0
STEP_DOWN_DB: float = 10.0          # decrease after heard response (Hughson-Westlake)
STEP_UP_DB: float = 5.0             # increase after no response
MAX_ASCENDING_RUNS: int = 8
THRESHOLD_RESPONSES_NEEDED: int = 2
THRESHOLD_WINDOW: int = 3
# Safety-net cap on total presentations per frequency. High enough that a
# legitimate staircase (~11 presentations to satisfy the 2-of-3 rule, up to
# MAX_ASCENDING_RUNS) converges; it only ever fires on a degenerate
# miss-everything pattern. Hearing-everything is handled earlier and faster by
# flooring detection (below), so good hearing no longer "drags on".
MAX_PRESENTATIONS: int = 30
# Hearing the test floor (MIN_LEVEL_DBFS) this many times means the volume is too
# high to bracket a threshold: terminate early and flag the frequency floored.
FLOOR_HEARD_LIMIT: int = 2
RESPONSE_WINDOW_S: float = 2.0

# ── Compensation parameters ───────────────────────────────────────────────────

GAIN_FRACTION: float = 0.50         # half-gain rule (Lybarger 1944)
MAX_COMPENSATION_DB: float = 12.0
# Self-administered, uncalibrated thresholds have ~5 dB+ test-retest spread
# (Saliba et al. 2022, AJA), and the half-gain rule over-prescribes for mild
# losses (Schwartz et al. 1980). Ignore measured "loss" below this deadband so
# we don't EQ within-noise differences. See docs/designs/measurement-resolution-eq.md.
HEARING_DEADBAND_DB: float = 10.0
# Deadband for the relative model: applied to the *smoothed* per-frequency
# deviation. Lower than the absolute deadband because smoothing already rejects
# single-point noise, so a smaller bar catches mild-but-consistent deviations.
RELATIVE_DEADBAND_DB: float = 6.0
# Per-point inherent uncertainty even with repeats (avoids div-by-zero and reflects
# that no self-test point is perfectly reliable). Used by the noise-aware model.
NOISE_FLOOR_DB: float = 2.0
# L/R deviations within POOL_SIGMA combined std are pooled (treated as the same);
# a correction must exceed GATE_SIGMA of its own (smoothed) noise to be applied.
POOL_SIGMA: float = 1.0
GATE_SIGMA: float = 1.0
# Across-frequency smoothing kernel width, in octaves. Weighting by log-frequency
# distance (not list position) keeps a real deviation from being washed out by a
# distant frequency when intervening frequencies are missing/floored.
SMOOTH_SIGMA_OCT: float = 0.6
# Adaptive depth: every frequency gets 1 pass; a frequency whose deviation looks
# like a candidate for correction is repeated (up to MEASUREMENT_REPEATS) to confirm
# it and measure its spread. Clean/normal frequencies finish in one pass — fast where
# it's easy, careful where it matters. The reference (1 kHz) always gets >=2 passes.
MEASUREMENT_REPEATS: int = 3
ADAPTIVE_TRIGGER_DB: float = 4.0
ASYMMETRY_WARNING_DB: float = 15.0
NOISE_GATE_THRESHOLD_DBFS: float = -30.0

# ── Normal hearing reference ──────────────────────────────────────────────────
#
# Expected threshold level (dBFS) for a young adult with normal hearing at a
# comfortable music-listening volume. These values are used to convert a
# measured threshold into an estimated hearing loss. Since we lack
# device-specific RETSPL calibration the same reference is used for all
# headphone models; the user anchors the test by setting a consistent volume.
#
# Values are derived from ISO 7029:2017 median data (young adult, 18–25 yrs)
# mapped to our relative dBFS scale by assuming comfortable playback sits at
# roughly –20 dBFS RMS and that the test starting level (–20 dBFS peak) is
# about 30 dB above the expected threshold for a normal-hearing listener.

NORMAL_HEARING_REFERENCE: dict[int, float] = {
    250:  -45.0,   # heuristic dBFS mapping (this whole table is softened, not raw
                   # RETSPL); ~3 dB less sensitive than 500 Hz, matching the curve's
                   # own LF compression. Not used by PTA4 (250 is excluded), so it
                   # only affects the legacy absolute compensation path.
    500:  -48.0,
    1000: -50.0,
    2000: -50.0,
    3000: -49.0,
    4000: -47.0,
    6000: -44.0,
    8000: -42.0,
    # Extended high frequencies (opt-in). Anchored at 8 kHz (-42.0) plus the raw
    # ISO 389-5:2006 RETSPL increment over 8 kHz (RETSPL(8000)=17.5): the steep,
    # physically-real EHF rise is kept un-softened. RETSPL(10k/12.5k/16k)=22.0/27.5/53.0.
    10000: -37.5,  # -42.0 + (22.0 - 17.5)
    12500: -32.0,  # -42.0 + (27.5 - 17.5)
    16000: -6.5,   # -42.0 + (53.0 - 17.5)
}

HEARING_PROFILE_FILENAME = "hearing_profile.json"

# Normal threshold shape, relative to 1 kHz, at the audiometric test frequencies.
# Derived from ISO 389-8:2004 RETSPL (HDA 200 circumaural earphone) — reference
# threshold-of-hearing levels, i.e. the *threshold* shape appropriate for a
# threshold-based test (not ISO 226 supra-threshold loudness contours). Subtracting
# this isolates the listener's deviation from a normal ear's natural frequency
# response so we don't over-correct the extremes.
# See docs/designs/calibration-robust-hearing.md.
NORMAL_RELATIVE_SHAPE_DB: dict[int, float] = {
    250: 12.5, 500: 5.5, 1000: 0.0, 2000: -1.0, 3000: -3.0, 4000: 4.0, 6000: 11.5, 8000: 12.0,
    # Extended high frequencies (opt-in), from ISO 389-5:2006 Table 1 (HDA 200,
    # IEC 60318-1): RETSPL(10k/12.5k/16k)=22.0/27.5/53.0 dB SPL, minus 5.5.
    10000: 16.5, 12500: 22.0, 16000: 47.5,
}
# Every entry = ISO 389-8:2004 (≤8 kHz) / ISO 389-5:2006 (>8 kHz) Table 1 RETSPL(f)
# − RETSPL(1000), where RETSPL(1000) = 5.5 dB. Verified against the standards:
#   250→18.0  500→11.0  2000→4.5  3000→2.5  4000→9.5  6000→17.0  8000→17.5
#   10000→22.0  12500→27.5  16000→53.0 dB SPL.

# WHO 2021 grades of hearing loss, keyed by better-ear pure-tone average (dB).
# Each entry is (exclusive upper bound, label); the last bound is +inf.
WHO_GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (20.0, "No impairment"),
    (35.0, "Mild"),
    (50.0, "Moderate"),
    (65.0, "Moderately severe"),
    (80.0, "Severe"),
    (95.0, "Profound"),
    (float("inf"), "Complete"),
)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FrequencyThreshold:
    freq_hz: int
    level_dbfs: Optional[float]  # None when UNDETERMINED
    ascending_runs: int
    determined: bool             # True only when the staircase truly converged
    floored: bool = False        # heard the test floor -> volume likely too high
    spread_db: float = 0.0        # std of the repeated passes (per-point uncertainty)


@dataclass
class HearingProfile:
    left: dict[int, FrequencyThreshold]
    right: dict[int, FrequencyThreshold]
    tested_at: str                  # ISO 8601
    asymmetric_freqs: list[int]     # freqs where L/R gap > ASYMMETRY_WARNING_DB
    # False-positive (catch-trial) accounting, e.g.
    # {"left": {"catch": 6, "false_positive": 1}, "right": {...}}. Optional so
    # older saved profiles (written before this field existed) still load.
    catch_stats: Optional[dict] = None
    unreliable_ears: Optional[list] = None  # subset of ["left", "right"]

    def to_dict(self) -> dict:
        return {
            "tested_at": self.tested_at,
            "asymmetric_freqs": self.asymmetric_freqs,
            "catch_stats": self.catch_stats,
            "unreliable_ears": self.unreliable_ears,
            "left": {str(k): asdict(v) for k, v in self.left.items()},
            "right": {str(k): asdict(v) for k, v in self.right.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HearingProfile":
        def _parse_side(side: dict) -> dict[int, FrequencyThreshold]:
            return {
                int(k): FrequencyThreshold(**v)
                for k, v in side.items()
            }
        return cls(
            left=_parse_side(data["left"]),
            right=_parse_side(data["right"]),
            tested_at=data["tested_at"],
            asymmetric_freqs=data.get("asymmetric_freqs", []),
            catch_stats=data.get("catch_stats"),
            unreliable_ears=data.get("unreliable_ears"),
        )


# ── Threshold engine ──────────────────────────────────────────────────────────

class ThresholdEngine:
    """
    Single-ear, single-frequency pure-tone threshold state machine.

    Modified Hughson-Westlake procedure (Carhart & Jerger 1959):
    - Decrease 10 dB after a heard response.
    - Increase 5 dB after a missed response (entering an ascending run).
    - An ascending run completes when the user hears the tone while ascending.
    - Threshold = lowest level heard on ≥ 2 of the last 3 ascending runs.
    - Minimum 3 ascending runs required before threshold can be declared.
    - Maximum MAX_ASCENDING_RUNS runs; best estimate used if not stable.
    """

    def __init__(self, freq_hz: int, start_level_dbfs: float = START_LEVEL_DBFS) -> None:
        self.freq_hz = freq_hz
        self._level = float(start_level_dbfs)
        self._in_ascending = False  # True after at least one miss in current run
        self._run_count = 0         # completed ascending runs
        self._ascending_hits: list[float] = []
        self._done = False
        self._threshold: float | None = None
        self._presentations = 0     # total tones presented (safety cap)
        self._ever_heard = False    # any heard response at all
        self._converged = False     # True only on real 2-of-3 convergence
        self._floored = False       # heard the test floor (volume too high)
        self._floor_heard = 0       # times the floor was heard

    @property
    def current_level_dbfs(self) -> float:
        return self._level

    @property
    def done(self) -> bool:
        return self._done

    @property
    def threshold(self) -> float | None:
        return self._threshold

    @property
    def ascending_run_count(self) -> int:
        return self._run_count

    @property
    def converged(self) -> bool:
        """True only when a real threshold was found (>=3 ascending runs,
        2-of-last-3). Cap-terminated / floored results are NOT converged."""
        return self._converged

    @property
    def floored(self) -> bool:
        """True if the listener heard the test floor — volume likely too high."""
        return self._floored

    def record_response(self, heard: bool) -> None:
        """Feed one user response for the current level."""
        if self._done:
            return

        self._presentations += 1
        if heard:
            self._ever_heard = True
            # Flooring: heard the quietest tone -> can't bracket a threshold.
            # Terminate early and flag it (the test should tell the user to lower
            # the volume) rather than grinding to the safety cap.
            if self._level <= MIN_LEVEL_DBFS:
                self._floored = True
                self._floor_heard += 1
                if self._floor_heard >= FLOOR_HEARD_LIMIT:
                    self._threshold = None
                    self._done = True
                    return
            if self._in_ascending:
                self._run_count += 1
                self._ascending_hits.append(round(self._level, 2))
                threshold = self._check_threshold()
                if threshold is not None:
                    self._threshold = threshold
                    self._converged = True
                    self._done = True
                    return
                if self._run_count >= MAX_ASCENDING_RUNS:
                    self._threshold = self._best_estimate()
                    self._done = True
                    return
            # Step down after response
            self._level = max(MIN_LEVEL_DBFS, self._level - STEP_DOWN_DB)
            self._in_ascending = False
        else:
            # Step up; mark ascending phase
            self._level = min(MAX_LEVEL_DBFS, self._level + STEP_UP_DB)
            self._in_ascending = True

        # Safety cap: guarantee termination even when the staircase never
        # produces an ascending run (listener hears or misses everything).
        if not self._done and self._presentations >= MAX_PRESENTATIONS:
            est = self._best_estimate()
            if est is not None:
                self._threshold = est
            elif self._ever_heard:
                # Heard even the quietest tone -> threshold at/near the floor.
                self._threshold = round(self._level, 2)
            else:
                # Never heard anything -> threshold genuinely undetermined.
                self._threshold = None
            self._done = True

    def _check_threshold(self) -> float | None:
        if self._run_count < 3:
            return None
        recent = self._ascending_hits[-THRESHOLD_WINDOW:]
        counts = Counter(recent)
        candidates = [lev for lev, cnt in counts.items() if cnt >= THRESHOLD_RESPONSES_NEEDED]
        return min(candidates) if candidates else None

    def _best_estimate(self) -> float | None:
        if not self._ascending_hits:
            return None
        counts = Counter(self._ascending_hits)
        return min(counts, key=lambda lev: (-counts[lev], lev))


# ── Tone generation ───────────────────────────────────────────────────────────

def generate_tone(freq_hz: int, level_dbfs: float, sample_rate: int = 48000,
                  ear: str = "both") -> np.ndarray:
    """
    Return a stereo (N, 2) float64 buffer: a pure sine at freq_hz scaled to
    level_dbfs, with 30 ms raised-cosine onset and offset ramps.

    ``ear`` routes the tone to a single channel so that a one-ear threshold
    test is actually measured in that ear: "left" silences the right channel,
    "right" silences the left, and "both" (default) plays the tone in both.
    """
    n_total = int(round(TONE_DURATION_S * sample_rate))
    n_ramp = int(round(RAMP_DURATION_S * sample_rate))

    t = np.arange(n_total, dtype=np.float64) / sample_rate
    mono = np.sin(2.0 * np.pi * freq_hz * t)

    if n_ramp > 0 and 2 * n_ramp <= n_total:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_ramp) / n_ramp))
        mono[:n_ramp] *= ramp
        mono[-n_ramp:] *= ramp[::-1]

    mono *= 10.0 ** (level_dbfs / 20.0)
    silent = np.zeros_like(mono)

    side = (ear or "both").lower()
    if side == "left":
        return np.column_stack([mono, silent])
    if side == "right":
        return np.column_stack([silent, mono])
    return np.column_stack([mono, mono])


def generate_silence(sample_rate: int = 48000) -> np.ndarray:
    """Return a silent stereo (N, 2) buffer the same length as a test tone.

    Used for catch trials: the listener is presented with nothing during the
    normal response window, so any response is a measurable false positive.
    """
    n_total = int(round(TONE_DURATION_S * sample_rate))
    return np.zeros((n_total, 2), dtype=np.float64)


def generate_tone_train(freq_hz: int, level_dbfs: float, sample_rate: int = 48000,
                        ear: str = "both", rng: Optional[random.Random] = None) -> np.ndarray:
    """Return a stereo (N, 2) buffer of a *pulsed* tone: a random number of pulses
    (PULSE_COUNT_MIN..PULSE_COUNT_MAX) at ``freq_hz``/``level_dbfs``, each
    PULSE_DURATION_S long with 30 ms raised-cosine ramps, separated by
    PULSE_GAP_S of silence.

    The random pulse count lets the listener confirm "I heard N beeps". Each pulse
    stays >= 0.20 s so temporal integration does not raise the threshold, and the
    whole train fits inside RESPONSE_WINDOW_S. ``ear`` routes exactly like
    ``generate_tone``. ``rng`` is injected for deterministic tests.
    """
    rng = rng or random.Random()
    n_pulses = rng.randint(PULSE_COUNT_MIN, PULSE_COUNT_MAX)

    n_pulse = int(round(PULSE_DURATION_S * sample_rate))
    n_gap = int(round(PULSE_GAP_S * sample_rate))
    n_ramp = int(round(RAMP_DURATION_S * sample_rate))

    t = np.arange(n_pulse, dtype=np.float64) / sample_rate
    pulse = np.sin(2.0 * np.pi * freq_hz * t)
    if n_ramp > 0 and 2 * n_ramp <= n_pulse:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_ramp) / n_ramp))
        pulse[:n_ramp] *= ramp
        pulse[-n_ramp:] *= ramp[::-1]
    pulse *= 10.0 ** (level_dbfs / 20.0)

    gap = np.zeros(n_gap, dtype=np.float64)
    segments: list[np.ndarray] = []
    for i in range(n_pulses):
        segments.append(pulse)
        if i < n_pulses - 1:
            segments.append(gap)
    mono = np.concatenate(segments)
    silent = np.zeros_like(mono)

    side = (ear or "both").lower()
    if side == "left":
        return np.column_stack([mono, silent])
    if side == "right":
        return np.column_stack([silent, mono])
    return np.column_stack([mono, mono])


# ── False-positive control (catch trials + jitter) ─────────────────────────────

def should_insert_catch(rng: random.Random, n_inserted_this_freq: int) -> bool:
    """Whether to present a silent catch trial before the next real tone."""
    return (n_inserted_this_freq < MAX_CATCH_TRIALS_PER_FREQ
            and rng.random() < CATCH_TRIAL_PROB)


def jittered_delay(rng: random.Random) -> float:
    """Pre-tone silence (seconds) drawn uniformly from [JITTER_MIN_S, JITTER_MAX_S]."""
    return rng.uniform(JITTER_MIN_S, JITTER_MAX_S)


def is_unreliable(catch_count: int, false_positive_count: int) -> bool:
    """True when an ear's false-positive rate is high enough to distrust it.

    Requires a minimum number of catch trials so a single early false positive
    doesn't flag the whole ear.
    """
    return catch_count >= 3 and (false_positive_count / catch_count) > FP_RATE_WARN


# ── Hearing summary (PTA4 + WHO grade) ─────────────────────────────────────────

def who_grade(better_ear_pta_db: float) -> str:
    """WHO 2021 hearing-loss grade for a better-ear pure-tone average (dB)."""
    for upper, label in WHO_GRADE_BANDS:
        if better_ear_pta_db < upper:
            return label
    return WHO_GRADE_BANDS[-1][1]


def _pta4(side: dict[int, "FrequencyThreshold"]) -> Optional[float]:
    """Estimated better-than-reference pure-tone average (dB) for one ear.

    est_HL(f) = threshold(f) − NORMAL_HEARING_REFERENCE[f] (positive = worse than
    normal). Requires at least 3 of the 4 PTA frequencies determined.
    """
    losses: list[float] = []
    for freq_hz in PTA4_FREQS:
        t = side.get(freq_hz)
        if t is not None and t.determined and t.level_dbfs is not None:
            losses.append(t.level_dbfs - NORMAL_HEARING_REFERENCE[freq_hz])
    if len(losses) < 3:
        return None
    return round(sum(losses) / len(losses), 1)


def compute_hearing_summary(profile: "HearingProfile") -> dict:
    """User-facing summary: per-ear PTA4, better-ear PTA, and WHO 2021 grade.

    Values are *estimates* from an uncalibrated self-test (relative dBFS, not
    clinical dB HL) — not a medical diagnosis. ``who_grade`` is None when fewer
    than 3 of the 4 PTA frequencies were determined in both ears.
    """
    pta_left = _pta4(profile.left)
    pta_right = _pta4(profile.right)
    present = [p for p in (pta_left, pta_right) if p is not None]
    better = min(present) if present else None
    return {
        "pta4_left_db": pta_left,
        "pta4_right_db": pta_right,
        "better_ear_pta_db": better,
        "who_grade": who_grade(better) if better is not None else None,
        "estimated": True,
    }


# ── Compensation curve ────────────────────────────────────────────────────────

def adaptive_needs_more_passes(
    freq_hz: int,
    levels: list[float],
    reference_dbfs: Optional[float],
    attempts: int,
    *,
    min_passes: int = 1,
    max_passes: int = MEASUREMENT_REPEATS,
    trigger_db: float = ADAPTIVE_TRIGGER_DB,
) -> bool:
    """Whether to spend another measurement pass on this frequency (adaptive depth).

    Always do at least ``min_passes`` and never more than ``max_passes``. In between,
    repeat only if the running estimate looks deviant vs the reference (a candidate
    for correction worth confirming) — so clean frequencies finish in one pass.
    """
    if attempts >= max_passes:
        return False
    if attempts < min_passes:
        return True
    if not levels or reference_dbfs is None:
        return False
    mean = sum(levels) / len(levels)
    dev = (mean - reference_dbfs) - NORMAL_RELATIVE_SHAPE_DB.get(freq_hz, 0.0)
    return abs(dev) >= trigger_db


def averaged_frequency_threshold(
    freq_hz: int,
    levels: list[float],
    *,
    floored: bool,
    ascending_runs: int,
) -> "FrequencyThreshold":
    """Combine the converged thresholds from repeated passes at one frequency.

    Determined only if at least one pass converged and none floored; the level is
    the mean of the converged passes (finer than the 5 dB staircase grid).
    """
    if floored or not levels:
        return FrequencyThreshold(freq_hz, None, ascending_runs, False, floored)
    spread = round(float(np.std(levels)), 2) if len(levels) > 1 else 0.0
    return FrequencyThreshold(freq_hz, round(float(np.mean(levels)), 2), ascending_runs, True, False, spread)


def relative_compensation_points(
    side: dict[int, FrequencyThreshold],
    *,
    fraction: float = GAIN_FRACTION,
    deadband_db: float = RELATIVE_DEADBAND_DB,
    max_gain_db: float = MAX_COMPENSATION_DB,
) -> dict[int, float]:
    """Per-frequency EQ gain (dB) for one ear from a RELATIVE, calibration-invariant
    reading of its thresholds.

    Each determined threshold is referenced to the ear's own 1 kHz threshold (or the
    most sensitive determined frequency if 1 kHz is missing), the normal threshold
    shape (``NORMAL_RELATIVE_SHAPE_DB``) is subtracted to isolate the listener's
    deviation, and a fraction of any deviation beyond the noise deadband becomes a
    capped boost. Adding a constant to every threshold (a volume change) leaves the
    result unchanged — the absolute level cancels.
    """
    return _smooth_and_gate(_ear_deviations(side), fraction, deadband_db, max_gain_db)


def compute_relative_compensation(
    profile: HearingProfile,
    *,
    fraction: float = GAIN_FRACTION,
    deadband_db: float = RELATIVE_DEADBAND_DB,
    max_gain_db: float = MAX_COMPENSATION_DB,
) -> tuple[dict[int, float], dict[int, float]]:
    """Per-ear EQ gains using per-point uncertainty (from repeated passes):

    - A1 variance gate: a correction must exceed the deadband AND the point's own
      (smoothed) measured noise — so noisy points are not corrected.
    - B3 noise-aware pooling: where the two ears agree within their combined noise,
      the deviations are pooled (more data, less noise); where they reliably differ,
      each ear is kept separate — preserving real L/R asymmetry.
    - C4 uncertainty-weighted smoothing: neighbouring frequencies are blended with
      inverse-variance weights, so reliable points dominate noisy ones.
    """
    left = _ear_deviations(profile.left)
    right = _ear_deviations(profile.right)

    pooled_left: dict[int, tuple[float, float]] = {}
    pooled_right: dict[int, tuple[float, float]] = {}
    for freq_hz in sorted(set(left) | set(right)):
        dl = left.get(freq_hz)
        dr = right.get(freq_hz)
        if dl and dr:
            combined = math.hypot(dl[1], dr[1])
            if abs(dl[0] - dr[0]) <= POOL_SIGMA * combined:
                merged = _inverse_variance_weighted([dl, dr])  # ears agree -> pool
                pooled_left[freq_hz] = pooled_right[freq_hz] = merged
            else:
                pooled_left[freq_hz] = dl  # reliably differ -> per-ear
                pooled_right[freq_hz] = dr
        elif dl:
            pooled_left[freq_hz] = dl
        elif dr:
            pooled_right[freq_hz] = dr

    return (
        _smooth_and_gate(pooled_left, fraction, deadband_db, max_gain_db),
        _smooth_and_gate(pooled_right, fraction, deadband_db, max_gain_db),
    )


def _ear_deviations(side: dict[int, FrequencyThreshold]) -> dict[int, tuple[float, float]]:
    """{freq: (deviation_db, noise_db)} for one ear — relative to its own 1 kHz,
    normal shape subtracted, with the combined measurement noise."""
    determined = {
        f: (t.level_dbfs, getattr(t, 'spread_db', 0.0) or 0.0)
        for f, t in side.items()
        if t is not None and t.determined and t.level_dbfs is not None
    }
    if len(determined) < 2:
        return {}
    ref_level, ref_spread = determined.get(1000, (None, 0.0))
    if ref_level is None:
        ref_level = min(v[0] for v in determined.values())
        ref_spread = 0.0
    ref_noise_sq = ref_spread ** 2 + NOISE_FLOOR_DB ** 2

    out: dict[int, tuple[float, float]] = {}
    for freq_hz, (level, spread) in determined.items():
        dev = (level - ref_level) - NORMAL_RELATIVE_SHAPE_DB.get(freq_hz, 0.0)
        noise = math.sqrt(spread ** 2 + NOISE_FLOOR_DB ** 2 + ref_noise_sq)
        out[freq_hz] = (dev, noise)
    return out


def _inverse_variance_weighted(items: list[tuple[float, float]]) -> tuple[float, float]:
    weights = [1.0 / (n * n) for _, n in items]
    total = sum(weights)
    dev = sum(w * d for w, (d, _) in zip(weights, items)) / total
    return dev, (1.0 / total) ** 0.5


def _smooth_and_gate(dn: dict[int, tuple[float, float]], fraction, deadband_db, max_gain_db) -> dict[int, float]:
    if not dn:
        return {}
    freqs = sorted(dn)
    devs = [dn[f][0] for f in freqs]
    noises = [dn[f][1] for f in freqs]
    # C4: smoothing weighted by log-frequency distance (Gaussian kernel) AND inverse
    # variance — neighbours blend by how close they actually are in frequency (so a
    # distant point doesn't wash out a real deviation) and how reliable they are.
    two_sigma_sq = 2.0 * SMOOTH_SIGMA_OCT ** 2
    sdev: list[float] = []
    snoise: list[float] = []
    for i, fi in enumerate(freqs):
        num = 0.0
        den = 0.0
        for j, fj in enumerate(freqs):
            oct_dist = abs(math.log2(fi / fj))
            if oct_dist > 1.5:
                continue  # negligible weight beyond ~1.5 octaves
            w = math.exp(-(oct_dist ** 2) / two_sigma_sq) / (noises[j] ** 2)
            num += w * devs[j]
            den += w
        sdev.append(num / den if den else devs[i])
        snoise.append((1.0 / den) ** 0.5 if den else noises[i])

    points: dict[int, float] = {}
    for freq_hz, d, n in zip(freqs, sdev, snoise):
        if d < deadband_db:
            continue  # within a normal ear / within self-test noise
        if d < GATE_SIGMA * n:
            continue  # A1: doesn't beat its own measured noise
        points[freq_hz] = round(float(np.clip(d * fraction, 0.0, max_gain_db)), 2)
    return points


def compute_compensation_points(profile: HearingProfile) -> dict[int, float]:
    """Half-gain EQ compensation (dB) at each *determined* audiometric frequency.

    Returns ``{freq_hz: gain_db}`` keyed by the frequencies actually present in
    the profile. L/R thresholds are averaged; undetermined frequencies are
    omitted. This is the raw, measurement-resolution compensation — the hearing
    test has only these few degrees of freedom, so the EQ is built directly from
    these points rather than from a dense interpolated grid. Iterating the
    profile's own frequencies (rather than a fixed list) lets opt-in extended
    high frequencies flow through when present.
    """
    points: dict[int, float] = {}
    for freq_hz in sorted(set(profile.left) | set(profile.right)):
        left_t = profile.left.get(freq_hz)
        right_t = profile.right.get(freq_hz)

        thresholds: list[float] = []
        if left_t is not None and left_t.determined and left_t.level_dbfs is not None:
            thresholds.append(left_t.level_dbfs)
        if right_t is not None and right_t.determined and right_t.level_dbfs is not None:
            thresholds.append(right_t.level_dbfs)
        if not thresholds:
            continue

        avg_threshold = float(np.mean(thresholds))
        ref = NORMAL_HEARING_REFERENCE.get(freq_hz, -50.0)
        loss = avg_threshold - ref  # positive = worse than reference
        if loss < HEARING_DEADBAND_DB:
            continue  # within self-test noise / clinically insignificant — don't EQ
        gain = float(np.clip(loss * GAIN_FRACTION, 0.0, MAX_COMPENSATION_DB))
        points[freq_hz] = round(gain, 2)
    return points


def _peaking_q_for_octave_bandwidth(n_octaves: float) -> float:
    """Q of a peaking filter whose -3 dB bandwidth spans ``n_octaves``.

    Standard relationship: Q = sqrt(2^N) / (2^N - 1). For N=1 octave Q≈1.41;
    for N=0.5 octave Q≈2.87.
    """
    n = max(0.05, float(n_octaves))
    return float((2.0 ** (n / 2.0)) / (2.0 ** n - 1.0))


def eq_bands_from_gain_points(
    points: dict[int, float],
    *,
    sample_rate: int | None = None,
    max_filters: int | None = None,
    max_gain_db: float = MAX_COMPENSATION_DB,
    min_gain_db: float = 0.1,
) -> list:
    """Build peaking PEQ bands placed directly at the measured frequencies.

    One peaking filter per frequency; each band's Q is derived from its spacing
    to neighbouring measured frequencies. When ``sample_rate`` is given, the band
    gains are solved by interaction-aware least squares so the realised chain
    matches the target points (overlapping bands sum) rather than each band
    taking its raw point gain. ``max_filters`` keeps the largest-magnitude bands.
    """
    from .peq import PEQBand, solve_band_gains_lsq

    freqs = sorted(points)
    if not freqs:
        return []
    logs = [np.log2(f) for f in freqs]

    qs: list[float] = []
    for i, _freq in enumerate(freqs):
        gaps = []
        if i > 0:
            gaps.append(logs[i] - logs[i - 1])
        if i < len(freqs) - 1:
            gaps.append(logs[i + 1] - logs[i])
        n_oct = float(np.mean(gaps)) if gaps else 1.0
        qs.append(round(min(4.5, max(0.5, _peaking_q_for_octave_bandwidth(n_oct))), 3))

    target = [float(points[f]) for f in freqs]
    if sample_rate:
        freqs_f = [float(f) for f in freqs]
        gains = solve_band_gains_lsq(freqs_f, target, sample_rate, freqs_f, qs, max_gain_db=max_gain_db)
    else:
        gains = [float(np.clip(g, -max_gain_db, max_gain_db)) for g in target]

    bands: list = [
        PEQBand("peaking", float(f), round(g, 2), q)
        for f, g, q in zip(freqs, gains, qs)
        if abs(g) >= min_gain_db
    ]
    if max_filters is not None and len(bands) > max_filters:
        bands = sorted(bands, key=lambda b: abs(b.gain_db), reverse=True)[:max_filters]
        bands.sort(key=lambda b: b.freq)
    return bands


def compute_compensation_curve(profile: HearingProfile, freq_grid: np.ndarray) -> np.ndarray:
    """
    Convert a HearingProfile to per-frequency EQ gain (dB) on freq_grid.

    Half-gain rule (Lybarger 1944):
        loss(f)  = measured_threshold(f) − NORMAL_HEARING_REFERENCE[f]
        gain(f)  = clamp(loss(f) × GAIN_FRACTION, 0, MAX_COMPENSATION_DB)

    L/R thresholds are averaged. Undetermined frequencies are skipped.
    The 7-point gain array is interpolated to freq_grid via cubic spline on
    log-frequency, then 1-octave Gaussian-smoothed to remove sharp peaks.
    """
    points = compute_compensation_points(profile)
    if len(points) < 2:
        return np.zeros(len(freq_grid))

    test_freqs = [float(f) for f in sorted(points)]
    test_gains = [points[int(f)] for f in test_freqs]

    log_test = np.log10(test_freqs)
    cs = CubicSpline(log_test, test_gains, bc_type="not-a-knot", extrapolate=True)

    log_grid = np.log10(np.maximum(freq_grid, 1.0))
    raw = cs(log_grid)
    raw = np.clip(raw, 0.0, MAX_COMPENSATION_DB)

    # 1-octave Gaussian smoothing to prevent sharp EQ transitions
    smoothed = fractional_octave_smoothing(freq_grid, raw, fraction=1.0)
    return np.maximum(smoothed, 0.0)  # type: ignore[no-any-return]


def detect_asymmetric_frequencies(profile_left: dict[int, FrequencyThreshold],
                                   profile_right: dict[int, FrequencyThreshold]) -> list[int]:
    """Return frequencies where L/R threshold gap exceeds ASYMMETRY_WARNING_DB."""
    asymmetric = []
    for freq_hz in TEST_FREQUENCIES:
        left_t = profile_left.get(freq_hz)
        right_t = profile_right.get(freq_hz)
        if (
            left_t is not None and left_t.determined and left_t.level_dbfs is not None
            and right_t is not None and right_t.determined and right_t.level_dbfs is not None
        ):
            gap = abs(left_t.level_dbfs - right_t.level_dbfs)
            if gap > ASYMMETRY_WARNING_DB:
                asymmetric.append(freq_hz)
    return asymmetric


# ── Persistence ───────────────────────────────────────────────────────────────

def save_hearing_profile(profile: HearingProfile) -> Path:
    """Write profile to the platform config directory."""
    path = config_dir() / HEARING_PROFILE_FILENAME
    path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    return path


def load_hearing_profile() -> Optional[HearingProfile]:
    """Return the saved profile, or None if none exists or it is unreadable."""
    path = config_dir() / HEARING_PROFILE_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return HearingProfile.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def hearing_profile_path() -> Path:
    return config_dir() / HEARING_PROFILE_FILENAME


# ── CLI test runner ───────────────────────────────────────────────────────────

def run_cli_hearing_test(
    backend,
    output_device: str | None,
    sample_rate: int = 48000,
    *,
    on_status=None,
    rng: random.Random | None = None,
    extended_hf: bool = False,
) -> HearingProfile:
    """
    Headless hearing test runner for CLI / TUI use.

    Plays each pulsed tone train via backend.play_tone(). The user presses Enter
    to indicate they heard the tone; a response window timer handles silence.
    Silent catch trials and jittered timing suppress and measure false-positive
    ("phantom") responses. With ``extended_hf`` the opt-in 10/12.5/16 kHz set is
    also measured. Returns a completed HearingProfile.
    """
    import sys
    import threading

    rng = rng or random.Random()
    test_order = build_test_order(extended_hf)

    def _status(msg: str) -> None:
        if on_status:
            on_status(msg)
        else:
            print(msg, flush=True)

    def _ask_heard(timeout_s: float) -> bool:
        """Return True if user presses Enter within timeout_s seconds."""
        heard_event = threading.Event()

        def _read():
            try:
                sys.stdin.readline()
                heard_event.set()
            except (EOFError, OSError):
                pass

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        return heard_event.wait(timeout=timeout_s)

    def _test_ear(ear_label: str) -> tuple[dict[int, FrequencyThreshold], int, int]:
        thresholds: dict[int, FrequencyThreshold] = {}
        processed: set[int] = set()
        reference: Optional[float] = None  # this ear's 1 kHz, for adaptive depth
        catch_count = 0          # silent trials presented for this ear
        false_positive_count = 0  # responses during a silent trial

        for freq_hz in test_order:
            if freq_hz in processed:
                continue
            processed.add(freq_hz)

            _status(f"\n  {ear_label} ear — {freq_hz} Hz")
            levels: list[float] = []
            floored = False
            runs = 0
            attempts = 0
            catch_this_freq = 0
            min_passes = 2 if freq_hz == 1000 else 1
            while True:
                engine = ThresholdEngine(freq_hz, start_level_dbfs=START_LEVEL_DBFS)
                while not engine.done:
                    # Optional silent catch trial before the real tone: a response
                    # to silence is a false positive (does NOT advance the staircase).
                    if should_insert_catch(rng, catch_this_freq):
                        catch_this_freq += 1
                        catch_count += 1
                        backend.play_tone(generate_silence(sample_rate), sample_rate, output_device)
                        if _ask_heard(RESPONSE_WINDOW_S):
                            false_positive_count += 1
                    time.sleep(jittered_delay(rng))  # break the predictable rhythm
                    level = engine.current_level_dbfs
                    samples = generate_tone_train(freq_hz, level, sample_rate, ear=ear_label.lower(), rng=rng)
                    backend.play_tone(samples, sample_rate, output_device)
                    heard = _ask_heard(RESPONSE_WINDOW_S)
                    engine.record_response(heard)
                attempts += 1
                runs = max(runs, engine.ascending_run_count)
                if engine.floored:
                    floored = True
                    break  # volume too high — no point repeating
                if engine.converged and engine.threshold is not None:
                    levels.append(engine.threshold)
                if not adaptive_needs_more_passes(freq_hz, levels, reference, attempts, min_passes=min_passes):
                    break

            result = averaged_frequency_threshold(freq_hz, levels, floored=floored, ascending_runs=runs)
            thresholds[freq_hz] = result
            if freq_hz == 1000 and result.determined:
                reference = result.level_dbfs
            if result.determined:
                _status(f"    threshold: {result.level_dbfs:.1f} dBFS (avg of {len(levels)})")
            elif floored:
                _status("    floored — volume too high to measure; lower it and retest")
            else:
                _status(f"    threshold undetermined after {runs} runs")

        return thresholds, catch_count, false_positive_count

    _status("\n=== Hearing Threshold Test ===")
    _status("Instructions:")
    _status("  Set your headphone volume to a comfortable music-listening level.")
    _status("  Press Enter each time you hear a tone. Stay still and quiet.")
    _status("  If you do not hear the tone, do nothing — the test will advance.")
    _status("\nStarting left ear. Cover or plug your right ear.")
    input("  Press Enter to begin...")

    left, left_catch, left_fp = _test_ear("Left")

    _status("\nRight ear. Cover or plug your left ear.")
    input("  Press Enter to continue...")

    right, right_catch, right_fp = _test_ear("Right")

    asymmetric = detect_asymmetric_frequencies(left, right)

    catch_stats = {
        "left": {"catch": left_catch, "false_positive": left_fp},
        "right": {"catch": right_catch, "false_positive": right_fp},
    }
    unreliable_ears = [
        ear for ear, s in catch_stats.items()
        if is_unreliable(s["catch"], s["false_positive"])
    ]
    if unreliable_ears:
        _status(
            "\n⚠ High false-positive rate detected for "
            f"{', '.join(unreliable_ears)} ear(s). Results may be unreliable — "
            "consider retesting in a quieter setting and responding only to tones "
            "you are sure you hear."
        )

    profile = HearingProfile(
        left=left,
        right=right,
        tested_at=datetime.now(timezone.utc).isoformat(),
        asymmetric_freqs=asymmetric,
        catch_stats=catch_stats,
        unreliable_ears=unreliable_ears,
    )
    return profile
