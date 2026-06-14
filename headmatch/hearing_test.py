"""Hearing threshold measurement and EQ compensation.

Implements the Modified Hughson-Westlake pure-tone threshold procedure
(Carhart & Jerger 1959, public domain) and the half-gain EQ compensation
rule (Lybarger 1944, public domain).

No proprietary algorithm or patented DSP method is used.
"""
from __future__ import annotations

import json
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

TEST_FREQUENCIES: tuple[int, ...] = (500, 1000, 2000, 3000, 4000, 6000, 8000)

# ISO 8253-1 test order: start at 1 kHz, ascend, re-verify 1 kHz, descend.
# The duplicate 1000 Hz entry allows reliability verification.
TEST_ORDER: tuple[int, ...] = (1000, 2000, 3000, 4000, 6000, 8000, 1000, 500)

# ── Tone stimulus parameters ──────────────────────────────────────────────────

TONE_DURATION_S: float = 1.0
INTER_TONE_SILENCE_S: float = 0.8
RAMP_DURATION_S: float = 0.03       # 30 ms raised-cosine onset/offset

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
RESPONSE_WINDOW_S: float = 3.0

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
# Each frequency is measured this many times and the converged thresholds are
# averaged, to cut the per-point self-test variability that makes a single pass
# jagged (Saliba et al. 2022: within-5 dB agreement only 60-77% per frequency).
MEASUREMENT_REPEATS: int = 2
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
    500:  -48.0,
    1000: -50.0,
    2000: -50.0,
    3000: -49.0,
    4000: -47.0,
    6000: -44.0,
    8000: -42.0,
}

HEARING_PROFILE_FILENAME = "hearing_profile.json"

# Normal threshold shape, relative to 1 kHz, at the audiometric test frequencies.
# Derived from ISO 389-8:2004 RETSPL (HDA 200 circumaural earphone) — reference
# threshold-of-hearing levels, i.e. the *threshold* shape appropriate for a
# threshold-based test (not ISO 226 supra-threshold loudness contours). Subtracting
# this isolates the listener's deviation from a normal ear's natural frequency
# response so we don't over-correct the extremes. 6 kHz is log-f interpolated (not
# in the ISO 389-8 table). See docs/designs/calibration-robust-hearing.md.
NORMAL_RELATIVE_SHAPE_DB: dict[int, float] = {
    500: 5.5, 1000: 0.0, 2000: -1.0, 3000: -3.0, 4000: 4.0, 6000: 8.7, 8000: 12.0,
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FrequencyThreshold:
    freq_hz: int
    level_dbfs: Optional[float]  # None when UNDETERMINED
    ascending_runs: int
    determined: bool             # True only when the staircase truly converged
    floored: bool = False        # heard the test floor -> volume likely too high


@dataclass
class HearingProfile:
    left: dict[int, FrequencyThreshold]
    right: dict[int, FrequencyThreshold]
    tested_at: str                  # ISO 8601
    asymmetric_freqs: list[int]     # freqs where L/R gap > ASYMMETRY_WARNING_DB

    def to_dict(self) -> dict:
        return {
            "tested_at": self.tested_at,
            "asymmetric_freqs": self.asymmetric_freqs,
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


# ── Compensation curve ────────────────────────────────────────────────────────

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
    return FrequencyThreshold(freq_hz, round(float(np.mean(levels)), 2), ascending_runs, True, False)


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
    thr = {
        f: t.level_dbfs
        for f, t in side.items()
        if t is not None and t.determined and t.level_dbfs is not None
    }
    if len(thr) < 2:
        return {}
    ref = thr.get(1000)
    if ref is None:
        ref = min(thr.values())  # most sensitive determined frequency

    freqs = sorted(thr)
    raw_dev = [(thr[f] - ref) - NORMAL_RELATIVE_SHAPE_DB.get(f, 0.0) for f in freqs]
    # Smooth across frequency (triangular 3-tap) so a single noisy self-test point
    # can't drive a boost — real hearing loss is smooth, so only deviations
    # corroborated by neighbouring frequencies survive.
    dev = _smooth_over_frequency(raw_dev)

    points: dict[int, float] = {}
    for freq_hz, d in zip(freqs, dev):
        if d < deadband_db:
            continue  # within a normal ear / within self-test noise
        points[freq_hz] = round(float(np.clip(d * fraction, 0.0, max_gain_db)), 2)
    return points


def _smooth_over_frequency(values: list[float]) -> list[float]:
    """Triangular 3-tap moving average (weights 0.25/0.5/0.25), edges renormalised."""
    n = len(values)
    out: list[float] = []
    for i in range(n):
        acc = 0.0
        weight = 0.0
        for j, w in ((i - 1, 0.25), (i, 0.5), (i + 1, 0.25)):
            if 0 <= j < n:
                acc += w * values[j]
                weight += w
        out.append(acc / weight if weight else values[i])
    return out


def compute_compensation_points(profile: HearingProfile) -> dict[int, float]:
    """Half-gain EQ compensation (dB) at each *determined* audiometric frequency.

    Returns ``{freq_hz: gain_db}`` keyed by the ISO 8253 test frequencies. L/R
    thresholds are averaged; undetermined frequencies are omitted. This is the
    raw, measurement-resolution compensation — the hearing test has only these
    ~7 degrees of freedom, so the EQ is built directly from these points rather
    than from a dense interpolated grid.
    """
    points: dict[int, float] = {}
    for freq_hz in TEST_FREQUENCIES:
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
        gains = solve_band_gains_lsq(freqs, target, sample_rate, freqs, qs, max_gain_db=max_gain_db)
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
) -> HearingProfile:
    """
    Headless hearing test runner for CLI / TUI use.

    Plays each tone via backend.play_tone(). The user presses Enter to
    indicate they heard the tone; a response window timer handles silence.
    Returns a completed HearingProfile.
    """
    import sys
    import threading

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

    def _test_ear(ear_label: str) -> dict[int, FrequencyThreshold]:
        thresholds: dict[int, FrequencyThreshold] = {}
        processed: set[int] = set()

        for freq_hz in TEST_ORDER:
            if freq_hz in processed:
                continue
            processed.add(freq_hz)

            _status(f"\n  {ear_label} ear — {freq_hz} Hz")
            levels: list[float] = []
            floored = False
            runs = 0
            for _rep in range(MEASUREMENT_REPEATS):
                engine = ThresholdEngine(freq_hz, start_level_dbfs=START_LEVEL_DBFS)
                while not engine.done:
                    level = engine.current_level_dbfs
                    samples = generate_tone(freq_hz, level, sample_rate, ear=ear_label.lower())
                    backend.play_tone(samples, sample_rate, output_device)
                    heard = _ask_heard(RESPONSE_WINDOW_S)
                    engine.record_response(heard)
                runs = max(runs, engine.ascending_run_count)
                if engine.floored:
                    floored = True
                    break  # volume too high — no point repeating
                if engine.converged and engine.threshold is not None:
                    levels.append(engine.threshold)

            result = averaged_frequency_threshold(freq_hz, levels, floored=floored, ascending_runs=runs)
            thresholds[freq_hz] = result
            if result.determined:
                _status(f"    threshold: {result.level_dbfs:.1f} dBFS (avg of {len(levels)})")
            elif floored:
                _status("    floored — volume too high to measure; lower it and retest")
            else:
                _status(f"    threshold undetermined after {runs} runs")

        return thresholds

    _status("\n=== Hearing Threshold Test ===")
    _status("Instructions:")
    _status("  Set your headphone volume to a comfortable music-listening level.")
    _status("  Press Enter each time you hear a tone. Stay still and quiet.")
    _status("  If you do not hear the tone, do nothing — the test will advance.")
    _status("\nStarting left ear. Cover or plug your right ear.")
    input("  Press Enter to begin...")

    left = _test_ear("Left")

    _status("\nRight ear. Cover or plug your left ear.")
    input("  Press Enter to continue...")

    right = _test_ear("Right")

    asymmetric = detect_asymmetric_frequencies(left, right)

    profile = HearingProfile(
        left=left,
        right=right,
        tested_at=datetime.now(timezone.utc).isoformat(),
        asymmetric_freqs=asymmetric,
    )
    return profile
