"""Tests for opt-in extended high frequencies (10, 12.5, 16 kHz).

See docs/superpowers/specs/2026-06-14-pulsed-tones-and-extended-high-frequencies-design.md
"""
from __future__ import annotations

import io
import random
import sys

from headmatch import hearing_test as ht_mod
from headmatch.hearing_test import (
    EXTENDED_HF_FREQUENCIES,
    NORMAL_HEARING_REFERENCE,
    NORMAL_RELATIVE_SHAPE_DB,
    PTA4_FREQS,
    TEST_FREQUENCIES,
    TEST_ORDER,
    FrequencyThreshold,
    HearingProfile,
    build_test_order,
    compute_compensation_points,
    compute_hearing_summary,
    run_cli_hearing_test,
)


class TestExtendedHfConstants:
    def test_ehf_set(self):
        assert EXTENDED_HF_FREQUENCIES == (10000, 12500, 16000)

    def test_ehf_not_in_default_frequencies(self):
        for f in EXTENDED_HF_FREQUENCIES:
            assert f not in TEST_FREQUENCIES

    def test_ehf_excluded_from_pta4(self):
        for f in EXTENDED_HF_FREQUENCIES:
            assert f not in PTA4_FREQS

    def test_relative_shape_values_from_iso_389_5(self):
        # RETSPL(f) - RETSPL(1000)=5.5 from ISO 389-5:2006 (HDA 200, IEC 60318-1).
        assert NORMAL_RELATIVE_SHAPE_DB[10000] == 16.5   # 22.0 - 5.5
        assert NORMAL_RELATIVE_SHAPE_DB[12500] == 22.0   # 27.5 - 5.5
        assert NORMAL_RELATIVE_SHAPE_DB[16000] == 47.5   # 53.0 - 5.5

    def test_absolute_reference_values_present(self):
        # Anchored at 8 kHz (-42.0) plus raw RETSPL increment over 8 kHz (17.5).
        assert NORMAL_HEARING_REFERENCE[10000] == -37.5
        assert NORMAL_HEARING_REFERENCE[12500] == -32.0
        assert NORMAL_HEARING_REFERENCE[16000] == -6.5


class TestBuildTestOrder:
    def test_default_order_unchanged(self):
        assert build_test_order(False) == TEST_ORDER

    def test_extended_order_contains_ehf(self):
        order = build_test_order(True)
        for f in EXTENDED_HF_FREQUENCIES:
            assert f in order

    def test_ehf_placed_after_8000_before_low_descent(self):
        order = build_test_order(True)
        assert order.index(10000) > order.index(8000)
        assert order.index(12500) > order.index(10000)
        assert order.index(16000) > order.index(12500)
        # EHF sits before the final low-frequency descent (500/250).
        assert order.index(16000) < order.index(500)

    def test_extended_order_keeps_all_standard_frequencies(self):
        order = build_test_order(True)
        for f in TEST_FREQUENCIES:
            assert f in order


def _side(levels: dict[int, float]) -> dict[int, FrequencyThreshold]:
    return {f: FrequencyThreshold(f, levels[f], 3, True) for f in levels}


class TestCompensationPointsWithEhf:
    def test_ehf_point_included_when_present_and_deviant(self):
        # A big loss at 12.5 kHz (well beyond the normal reference + deadband).
        levels = {1000: NORMAL_HEARING_REFERENCE[1000],
                  12500: NORMAL_HEARING_REFERENCE[12500] + 30.0}
        points = compute_compensation_points(HearingProfile(
            left=_side(levels), right=_side(levels), tested_at="t", asymmetric_freqs=[]))
        assert 12500 in points and points[12500] > 0

    def test_frequencies_absent_from_profile_excluded(self):
        # Only 1 kHz present -> no EHF, no other frequencies in the output.
        levels = {1000: NORMAL_HEARING_REFERENCE[1000] + 30.0}
        points = compute_compensation_points(HearingProfile(
            left=_side(levels), right=_side(levels), tested_at="t", asymmetric_freqs=[]))
        assert set(points).issubset({1000})

    def test_pta4_unaffected_by_ehf(self):
        base = {f: NORMAL_HEARING_REFERENCE[f] + 30.0 for f in PTA4_FREQS}
        without = compute_hearing_summary(HearingProfile(
            left=_side(base), right=_side(base), tested_at="t", asymmetric_freqs=[]))
        with_ehf = dict(base); with_ehf[16000] = NORMAL_HEARING_REFERENCE[16000] + 40.0
        got = compute_hearing_summary(HearingProfile(
            left=_side(with_ehf), right=_side(with_ehf), tested_at="t", asymmetric_freqs=[]))
        assert got["pta4_left_db"] == without["pta4_left_db"]


# ── Runner integration ──────────────────────────────────────────────────────

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
    def play_tone(self, *a, **k):
        pass


def _patch_fast(monkeypatch):
    monkeypatch.setattr(ht_mod, "ThresholdEngine", _FakeEngine)
    monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.01)
    monkeypatch.setattr(ht_mod, "generate_tone_train", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod, "generate_silence", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))


def test_runner_default_has_no_ehf(monkeypatch):
    _patch_fast(monkeypatch)
    profile = run_cli_hearing_test(_FakeBackend(), None, 48000, rng=random.Random(1))
    for f in EXTENDED_HF_FREQUENCIES:
        assert f not in profile.left and f not in profile.right


def test_runner_extended_hf_measures_ehf(monkeypatch):
    _patch_fast(monkeypatch)
    profile = run_cli_hearing_test(_FakeBackend(), None, 48000, rng=random.Random(1),
                                   extended_hf=True)
    for f in EXTENDED_HF_FREQUENCIES:
        assert f in profile.left and f in profile.right
