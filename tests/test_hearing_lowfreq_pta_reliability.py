"""Tests for the 250 Hz addition, PTA4/WHO summary, and false-positive
(catch-trial + jitter) reliability handling in the hearing test.

See docs/superpowers/specs/2026-06-14-hearing-test-lowfreq-pta-who-reliability-design.md
"""
from __future__ import annotations

import io
import sys
import random

import pytest

from headmatch import hearing_test as ht_mod
from headmatch.hearing_test import (
    JITTER_MAX_S,
    JITTER_MIN_S,
    NORMAL_HEARING_REFERENCE,
    NORMAL_RELATIVE_SHAPE_DB,
    PTA4_FREQS,
    TEST_FREQUENCIES,
    TEST_ORDER,
    FrequencyThreshold,
    HearingProfile,
    compute_hearing_summary,
    is_unreliable,
    jittered_delay,
    run_cli_hearing_test,
    should_insert_catch,
    who_grade,
)


# ── Part A: 250 Hz ──────────────────────────────────────────────────────────

class Test250Hz:
    def test_250_in_test_frequencies(self):
        assert 250 in TEST_FREQUENCIES

    def test_test_order_ends_at_lowest(self):
        # ISO 8253-1 descends to the lowest frequency last.
        assert TEST_ORDER[-1] == 250

    def test_test_order_covers_all_frequencies(self):
        assert set(TEST_ORDER) == set(TEST_FREQUENCIES)

    def test_reference_values_present(self):
        assert 250 in NORMAL_HEARING_REFERENCE
        assert 250 in NORMAL_RELATIVE_SHAPE_DB

    def test_250_excluded_from_pta4(self):
        # PTA4 is the standard 500/1k/2k/4k average; 250 must not be in it.
        assert 250 not in PTA4_FREQS


# ── Part B: PTA4 + WHO grade ────────────────────────────────────────────────

def _threshold(freq_hz: int, level_dbfs: float | None, determined: bool = True):
    return FrequencyThreshold(freq_hz, level_dbfs, 3, determined)


def _profile(left_levels: dict[int, float], right_levels: dict[int, float] | None = None):
    if right_levels is None:
        right_levels = dict(left_levels)
    left = {f: _threshold(f, lv) for f, lv in left_levels.items()}
    right = {f: _threshold(f, lv) for f, lv in right_levels.items()}
    return HearingProfile(left=left, right=right, tested_at="2026-06-14T00:00:00+00:00",
                          asymmetric_freqs=[])


class TestWhoGrade:
    @pytest.mark.parametrize("pta,label", [
        (-5.0, "No impairment"),
        (19.9, "No impairment"),
        (20.0, "Mild"),
        (34.9, "Mild"),
        (35.0, "Moderate"),
        (49.9, "Moderate"),
        (50.0, "Moderately severe"),
        (64.9, "Moderately severe"),
        (65.0, "Severe"),
        (79.9, "Severe"),
        (80.0, "Profound"),
        (94.9, "Profound"),
        (95.0, "Complete"),
        (130.0, "Complete"),
    ])
    def test_boundaries(self, pta, label):
        assert who_grade(pta) == label


class TestComputeHearingSummary:
    def test_normal_hearing_no_impairment(self):
        # Thresholds exactly at the normal reference -> est_HL 0 -> No impairment.
        levels = {f: NORMAL_HEARING_REFERENCE[f] for f in PTA4_FREQS}
        summary = compute_hearing_summary(_profile(levels))
        assert summary["pta4_left_db"] == pytest.approx(0.0)
        assert summary["better_ear_pta_db"] == pytest.approx(0.0)
        assert summary["who_grade"] == "No impairment"
        assert summary["estimated"] is True

    def test_uniform_loss_grades_mild(self):
        # 30 dB worse than reference at all PTA frequencies -> PTA4 = 30 -> Mild.
        levels = {f: NORMAL_HEARING_REFERENCE[f] + 30.0 for f in PTA4_FREQS}
        summary = compute_hearing_summary(_profile(levels))
        assert summary["pta4_left_db"] == pytest.approx(30.0)
        assert summary["who_grade"] == "Mild"

    def test_better_ear_is_used(self):
        left = {f: NORMAL_HEARING_REFERENCE[f] + 60.0 for f in PTA4_FREQS}   # worse ear
        right = {f: NORMAL_HEARING_REFERENCE[f] + 10.0 for f in PTA4_FREQS}  # better ear
        summary = compute_hearing_summary(_profile(left, right))
        assert summary["better_ear_pta_db"] == pytest.approx(10.0)
        assert summary["who_grade"] == "No impairment"  # 10 < 20

    def test_insufficient_frequencies_gives_none(self):
        # Only 2 of the 4 PTA frequencies determined -> PTA undetermined.
        levels = {500: NORMAL_HEARING_REFERENCE[500], 1000: NORMAL_HEARING_REFERENCE[1000]}
        summary = compute_hearing_summary(_profile(levels))
        assert summary["pta4_left_db"] is None
        assert summary["better_ear_pta_db"] is None
        assert summary["who_grade"] is None

    def test_three_of_four_is_enough(self):
        levels = {f: NORMAL_HEARING_REFERENCE[f] for f in (500, 1000, 2000)}
        summary = compute_hearing_summary(_profile(levels))
        assert summary["pta4_left_db"] is not None

    def test_undetermined_threshold_excluded(self):
        levels = {f: NORMAL_HEARING_REFERENCE[f] for f in PTA4_FREQS}
        prof = _profile(levels)
        # Mark 4000 undetermined on the left -> still 3 of 4.
        prof.left[4000] = _threshold(4000, None, determined=False)
        summary = compute_hearing_summary(prof)
        assert summary["pta4_left_db"] is not None


class TestHearingSummaryInReport:
    def test_fit_report_includes_hearing_summary(self):
        from headmatch.pipeline import fit_from_hearing_profile
        levels = {f: NORMAL_HEARING_REFERENCE[f] + 30.0 for f in TEST_FREQUENCIES}
        _, _, report = fit_from_hearing_profile(_profile(levels), sample_rate=48000, max_filters=4)
        assert "hearing_summary" in report
        assert report["hearing_summary"]["who_grade"] == "Mild"
        assert report["hearing_summary"]["estimated"] is True


# ── Part C: catch trials + jitter ───────────────────────────────────────────

class _StubRng:
    """Deterministic stand-in: random() returns a fixed value, uniform echoes lo/hi."""
    def __init__(self, value: float):
        self._value = value

    def random(self) -> float:
        return self._value

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self._value


class TestShouldInsertCatch:
    def test_inserts_when_below_probability(self):
        assert should_insert_catch(_StubRng(0.1), 0) is True

    def test_skips_when_above_probability(self):
        assert should_insert_catch(_StubRng(0.9), 0) is False

    def test_respects_per_frequency_cap(self):
        from headmatch.hearing_test import MAX_CATCH_TRIALS_PER_FREQ
        assert should_insert_catch(_StubRng(0.0), MAX_CATCH_TRIALS_PER_FREQ) is False


class TestJitteredDelay:
    def test_within_bounds(self):
        rng = random.Random(0)
        for _ in range(200):
            d = jittered_delay(rng)
            assert JITTER_MIN_S <= d <= JITTER_MAX_S


class TestIsUnreliable:
    def test_high_false_positive_rate_is_unreliable(self):
        assert is_unreliable(catch_count=3, false_positive_count=2) is True  # 2/3 > 1/3

    def test_one_third_is_not_unreliable(self):
        assert is_unreliable(catch_count=3, false_positive_count=1) is False  # 1/3 not > 1/3

    def test_too_few_catches_never_unreliable(self):
        assert is_unreliable(catch_count=2, false_positive_count=2) is False

    def test_no_catches_is_safe(self):
        assert is_unreliable(catch_count=0, false_positive_count=0) is False


# ── Profile serialisation with new fields ───────────────────────────────────

class TestProfileSerialisation:
    def test_round_trip_with_catch_stats(self):
        levels = {f: -45.0 for f in TEST_FREQUENCIES}
        prof = _profile(levels)
        prof.catch_stats = {"left": {"catch": 5, "false_positive": 1},
                            "right": {"catch": 4, "false_positive": 0}}
        prof.unreliable_ears = ["left"]
        restored = HearingProfile.from_dict(prof.to_dict())
        assert restored.catch_stats == prof.catch_stats
        assert restored.unreliable_ears == ["left"]

    def test_back_compat_load_without_new_fields(self):
        # An old profile JSON lacking the reliability fields must still load.
        levels = {f: -45.0 for f in TEST_FREQUENCIES}
        data = _profile(levels).to_dict()
        data.pop("catch_stats", None)
        data.pop("unreliable_ears", None)
        restored = HearingProfile.from_dict(data)
        assert restored.catch_stats is None
        assert restored.unreliable_ears in (None, [])


# ── Runner integration: catch stats are collected ───────────────────────────

class _FakeEngine:
    def __init__(self, freq_hz, start_level_dbfs=-20.0):
        self.freq_hz = freq_hz
        self.current_level_dbfs = start_level_dbfs
        self._n = 0
        self.done = False
        self.threshold = -45.0
        self.ascending_run_count = 2
        self.converged = True
        self.floored = False

    def record_response(self, _heard):
        self._n += 1
        if self._n >= 2:
            self.done = True


class _FakeBackend:
    def __init__(self):
        self.calls = 0

    def play_tone(self, *a, **k):
        self.calls += 1


def _patch_fast(monkeypatch):
    monkeypatch.setattr(ht_mod, "ThresholdEngine", _FakeEngine)
    monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.01)
    monkeypatch.setattr(ht_mod, "generate_tone", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod, "generate_silence", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))


def test_runner_collects_catch_stats(monkeypatch):
    _patch_fast(monkeypatch)
    # Seed forces deterministic, reproducible catch insertion.
    profile = run_cli_hearing_test(_FakeBackend(), None, 48000, rng=random.Random(1))
    assert profile.catch_stats is not None
    assert set(profile.catch_stats) == {"left", "right"}
    total_catches = 0
    for ear in ("left", "right"):
        stats = profile.catch_stats[ear]
        assert stats["catch"] >= 0
        # A false positive can only occur on a catch trial.
        assert stats["false_positive"] <= stats["catch"]
        total_catches += stats["catch"]
    assert total_catches > 0  # the catch-trial path actually executed
    assert isinstance(profile.unreliable_ears, list)


def test_runner_flags_unreliable_when_all_responses_are_false_positives(monkeypatch):
    # This fake harness's _ask_heard returns True on empty stdin, so every catch
    # trial registers as a false positive -> both ears should be flagged unreliable.
    _patch_fast(monkeypatch)
    profile = run_cli_hearing_test(_FakeBackend(), None, 48000, rng=random.Random(1))
    assert set(profile.unreliable_ears) == {"left", "right"}
