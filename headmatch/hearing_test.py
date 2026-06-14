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
# Safety cap: the Hughson-Westlake staircase only completes via ascending runs,
# which require misses. A listener who hears (or misses) every presentation
# never produces an ascending run, so without this cap the frequency would
# never finish and the test would hang on it. 30 is well above a normal
# convergence (~10-20 presentations).
MAX_PRESENTATIONS: int = 30
RESPONSE_WINDOW_S: float = 3.0

# ── Compensation parameters ───────────────────────────────────────────────────

GAIN_FRACTION: float = 0.50         # half-gain rule (Lybarger 1944)
MAX_COMPENSATION_DB: float = 12.0
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


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FrequencyThreshold:
    freq_hz: int
    level_dbfs: Optional[float]  # None when UNDETERMINED
    ascending_runs: int
    determined: bool


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

    def record_response(self, heard: bool) -> None:
        """Feed one user response for the current level."""
        if self._done:
            return

        self._presentations += 1
        if heard:
            self._ever_heard = True
            if self._in_ascending:
                self._run_count += 1
                self._ascending_hits.append(round(self._level, 2))
                threshold = self._check_threshold()
                if threshold is not None:
                    self._threshold = threshold
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
    test_freqs: list[float] = []
    test_gains: list[float] = []

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
        gain = float(np.clip(loss * GAIN_FRACTION, 0.0, MAX_COMPENSATION_DB))

        test_freqs.append(float(freq_hz))
        test_gains.append(gain)

    if len(test_freqs) < 2:
        return np.zeros(len(freq_grid))

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

            engine = ThresholdEngine(freq_hz, start_level_dbfs=START_LEVEL_DBFS)
            _status(f"\n  {ear_label} ear — {freq_hz} Hz")

            while not engine.done:
                level = engine.current_level_dbfs
                samples = generate_tone(freq_hz, level, sample_rate, ear=ear_label.lower())
                backend.play_tone(samples, sample_rate, output_device)
                heard = _ask_heard(RESPONSE_WINDOW_S)
                engine.record_response(heard)

            threshold = engine.threshold
            determined = threshold is not None
            thresholds[freq_hz] = FrequencyThreshold(
                freq_hz=freq_hz,
                level_dbfs=threshold,
                ascending_runs=engine.ascending_run_count,
                determined=determined,
            )
            if determined:
                _status(f"    threshold: {threshold:.1f} dBFS after {engine.ascending_run_count} runs")
            else:
                _status(f"    threshold undetermined after {engine.ascending_run_count} runs")

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
