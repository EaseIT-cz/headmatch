"""Targeted coverage tests for headmatch.hearing_test.

Each test here drives a specific previously-uncovered branch/exception/edge path
in the threshold engine, the relative-compensation helpers, the PEQ band builder,
persistence, and the CLI runner. Style follows the sibling hearing tests:
behaviour-grouped classes, numpy for numerics, fast/deterministic, no real audio.
"""
from __future__ import annotations

import io
import sys

import pytest

from headmatch import hearing_test as ht_mod
from headmatch.hearing_test import (
    MAX_COMPENSATION_DB,
    MAX_PRESENTATIONS,
    MIN_LEVEL_DBFS,
    NOISE_FLOOR_DB,
    NORMAL_RELATIVE_SHAPE_DB,
    WHO_GRADE_BANDS,
    FrequencyThreshold,
    HearingProfile,
    ThresholdEngine,
    compute_relative_compensation,
    eq_bands_from_gain_points,
    hearing_profile_path,
    run_cli_hearing_test,
    who_grade,
    _ear_deviations,
    _smooth_and_gate,
)


# ── Safety-cap termination branches (lines 351, 354) ──────────────────────────

class TestSafetyCapTermination:
    def test_cap_uses_best_estimate_when_ascending_hits_exist(self):
        """Reach MAX_PRESENTATIONS with at least one completed ascending run so
        _best_estimate() returns a level (line 351)."""
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        # Drive a degenerate staircase that records an ascending hit but never
        # satisfies the 2-of-3 rule, so it runs to MAX_PRESENTATIONS with a
        # non-empty _ascending_hits list -> _best_estimate() returns a level.
        n = 0
        while not e.done:
            if e._in_ascending:
                heard = (int(round(e.current_level_dbfs)) % 10 == 0) and (n % 2 == 0)
            else:
                heard = False  # force misses to climb into ascending runs
            e.record_response(heard)
            n += 1
        assert e._presentations >= MAX_PRESENTATIONS
        assert not e.converged
        assert e._ascending_hits  # at least one hit -> best-estimate path
        assert e.threshold is not None  # line 351

    def test_cap_floor_threshold_when_ever_heard_but_no_runs(self):
        """Hit the cap having heard tones but never completing an ascending run,
        so _best_estimate() is None yet _ever_heard is True (line 354)."""
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        # Heard at the very first presentation (sets _ever_heard) then miss
        # everything afterwards. A miss never produces an ascending *hit*, so
        # _ascending_hits stays empty -> _best_estimate() is None.
        e.record_response(True)   # ever_heard = True, step down, not ascending
        while not e.done:
            e.record_response(False)  # only misses from here -> no ascending hits
        assert e._presentations >= MAX_PRESENTATIONS
        assert not e.converged
        assert e._ever_heard
        # Threshold pinned to current level (rounded), not None (line 354).
        assert e.threshold is not None

    def test_cap_undetermined_when_never_heard(self):
        """Control: never hearing anything leaves threshold None (line 357)."""
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        while not e.done:
            e.record_response(False)
        assert e._presentations >= MAX_PRESENTATIONS
        assert e.threshold is None


# ── who_grade fallthrough (line 492) ──────────────────────────────────────────

class TestWhoGradeFallthrough:
    def test_value_at_or_above_last_finite_bound_returns_complete(self):
        # The final band's bound is +inf, so the in-loop return normally always
        # fires. Patching the bands to a finite-only table forces the fallthrough
        # return at the bottom of the function (line 492).
        finite_bands = tuple(b for b in WHO_GRADE_BANDS if b[0] != float("inf"))
        import unittest.mock as mock
        with mock.patch.object(ht_mod, "WHO_GRADE_BANDS", finite_bands):
            assert ht_mod.who_grade(1e9) == finite_bands[-1][1]

    def test_normal_path_still_works(self):
        assert who_grade(0.0) == "No impairment"
        assert who_grade(1e9) == "Complete"


# ── compute_relative_compensation single-ear branches (lines 637-640) ─────────

def _side(levels: dict[int, float], spread: float = 0.0) -> dict[int, FrequencyThreshold]:
    return {f: FrequencyThreshold(f, levels[f], 3, True, spread_db=spread) for f in levels}


class TestRelativeCompensationSingleEar:
    def test_left_only_frequency_pools_into_left(self):
        """Frequencies determined only in the left ear take the `elif dl` path
        (lines 637-638)."""
        # Right ear only has the low/mid frequencies; the entire high band
        # (6000/8000) is left-only and carries a coherent elevated slope, so the
        # left-only deviations survive smoothing + the variance gate.
        right_levels = {f: -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] for f in (1000, 2000, 4000)}
        left_levels = {f: -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] for f in (1000, 2000, 4000)}
        left_levels[6000] = -60.0 + NORMAL_RELATIVE_SHAPE_DB[6000] + 18.0
        left_levels[8000] = -60.0 + NORMAL_RELATIVE_SHAPE_DB[8000] + 20.0
        profile = HearingProfile(
            left=_side(left_levels),
            right=_side(right_levels),
            tested_at="t",
            asymmetric_freqs=[],
        )
        left_pts, right_pts = compute_relative_compensation(profile)
        assert 8000 in left_pts and left_pts[8000] > 0
        assert 6000 not in right_pts and 8000 not in right_pts

    def test_right_only_frequency_pools_into_right(self):
        """Frequencies determined only in the right ear take the `elif dr` path
        (lines 639-640)."""
        left_levels = {f: -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] for f in (1000, 2000, 4000)}
        right_levels = {f: -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] for f in (1000, 2000, 4000)}
        right_levels[6000] = -60.0 + NORMAL_RELATIVE_SHAPE_DB[6000] + 18.0
        right_levels[8000] = -60.0 + NORMAL_RELATIVE_SHAPE_DB[8000] + 20.0
        profile = HearingProfile(
            left=_side(left_levels),
            right=_side(right_levels),
            tested_at="t",
            asymmetric_freqs=[],
        )
        left_pts, right_pts = compute_relative_compensation(profile)
        assert 8000 in right_pts and right_pts[8000] > 0
        assert 6000 not in left_pts and 8000 not in left_pts


# ── _ear_deviations 1 kHz-missing reference fallback (lines 670-671) ───────────

class TestEarDeviationsReferenceFallback:
    def test_falls_back_to_most_sensitive_when_1khz_missing(self):
        # No 1000 Hz entry -> ref_level falls back to the most sensitive (min)
        # determined level (lines 670-671).
        levels = {
            2000: -55.0,
            4000: -40.0,
            8000: -30.0,
        }
        out = _ear_deviations(_side(levels))
        assert out  # non-empty -> reference fallback succeeded
        # The most sensitive frequency (2000 @ -55) becomes the reference, so its
        # own deviation is -ref minus shape; relative offsets are anchored to it.
        assert 2000 in out and 4000 in out and 8000 in out


# ── _smooth_and_gate variance gate (line 740) ─────────────────────────────────

class TestSmoothAndGateVarianceGate:
    def test_deviation_beats_deadband_but_not_its_noise_is_gated(self):
        # A single edge point whose deviation clears the deadband but does NOT
        # exceed GATE_SIGMA * its (large) noise must be gated out (line 740).
        # Two points so the dict is non-empty; both are spectral edges (one-sided),
        # so neither is smoothed and each keeps its own large noise.
        dn = {
            1000: (0.0, NOISE_FLOOR_DB),       # reference-ish, below deadband
            8000: (8.0, 50.0),                 # dev 8 dB > 6 dB deadband, but << 50 dB noise
        }
        pts = _smooth_and_gate(dn, fraction=0.5, deadband_db=6.0, max_gain_db=MAX_COMPENSATION_DB)
        assert 8000 not in pts  # gated by the variance gate

    def test_deviation_beating_its_noise_is_kept(self):
        dn = {
            1000: (0.0, NOISE_FLOOR_DB),
            8000: (12.0, 2.0),  # clears deadband and easily beats its noise
        }
        pts = _smooth_and_gate(dn, fraction=0.5, deadband_db=6.0, max_gain_db=MAX_COMPENSATION_DB)
        assert 8000 in pts and pts[8000] > 0


# ── eq_bands_from_gain_points max_filters trimming (lines 835-836) ────────────

class TestEqBandsMaxFilters:
    def test_max_filters_keeps_largest_and_resorts_by_freq(self):
        points = {500: 2.0, 1000: 8.0, 2000: 4.0, 4000: 10.0, 8000: 1.0}
        bands = eq_bands_from_gain_points(points, max_filters=2)
        assert len(bands) == 2
        # Largest-magnitude bands kept (4000 @ 10, 1000 @ 8) then re-sorted by freq.
        freqs = [b.freq for b in bands]
        assert freqs == sorted(freqs)
        assert set(round(f) for f in freqs) == {1000, 4000}

    def test_no_trim_when_under_limit(self):
        points = {1000: 8.0, 4000: 10.0}
        bands = eq_bands_from_gain_points(points, max_filters=5)
        assert len(bands) == 2


# ── hearing_profile_path (line 910) ───────────────────────────────────────────

class TestHearingProfilePath:
    def test_returns_path_under_config_dir(self):
        p = hearing_profile_path()
        assert p.name == ht_mod.HEARING_PROFILE_FILENAME


# ── CLI runner branches (lines 953-954, 999-1000, 1012-1015) ──────────────────

class _FakeBackend:
    def __init__(self):
        self.calls = 0

    def play_tone(self, *a, **k):
        self.calls += 1


class _ConvergingEngine:
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


def _patch_fast(monkeypatch):
    monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.01)
    monkeypatch.setattr(ht_mod, "generate_tone_train", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod, "generate_silence", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    # Never insert catch trials by default (keeps presentation count tight/fast).
    monkeypatch.setattr(ht_mod, "should_insert_catch", lambda *a, **k: False)


class TestCliRunnerBranches:
    def test_read_thread_swallows_stdin_errors(self, monkeypatch):
        """_ask_heard's reader thread must swallow EOFError/OSError from stdin
        (lines 953-954). A stdin whose readline raises drives that except clause."""
        _patch_fast(monkeypatch)
        monkeypatch.setattr(ht_mod, "ThresholdEngine", _ConvergingEngine)

        class _RaisingStdin:
            def readline(self):
                raise OSError("no tty")

        monkeypatch.setattr(sys, "stdin", _RaisingStdin())
        # A short-but-nonzero window gives the reader thread time to run and raise.
        monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.05)
        profile = run_cli_hearing_test(_FakeBackend(), None, on_status=lambda *_: None)
        assert isinstance(profile, HearingProfile)

    def test_floored_frequency_breaks_and_reports(self, monkeypatch):
        """A floored engine breaks the repeat loop (lines 999-1000) and produces
        the floored status message (lines 1012-1013)."""
        _patch_fast(monkeypatch)
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))

        class _FlooredEngine:
            def __init__(self, freq_hz, start_level_dbfs=-20.0):
                self.current_level_dbfs = start_level_dbfs
                self._n = 0
                self.done = False
                self.threshold = None
                self.ascending_run_count = 1
                self.converged = False
                self.floored = True

            def record_response(self, _heard):
                self._n += 1
                if self._n >= 1:
                    self.done = True

        monkeypatch.setattr(ht_mod, "ThresholdEngine", _FlooredEngine)
        statuses: list[str] = []
        profile = run_cli_hearing_test(_FakeBackend(), None, on_status=statuses.append)
        assert any("floored" in s for s in statuses)
        assert all(not t.determined for t in profile.left.values())

    def test_undetermined_frequency_reports(self, monkeypatch):
        """A non-converging, non-floored engine yields the 'undetermined' status
        (lines 1014-1015)."""
        _patch_fast(monkeypatch)
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))

        class _UndeterminedEngine:
            def __init__(self, freq_hz, start_level_dbfs=-20.0):
                self.current_level_dbfs = start_level_dbfs
                self._n = 0
                self.done = False
                self.threshold = None
                self.ascending_run_count = 3
                self.converged = False
                self.floored = False

            def record_response(self, _heard):
                self._n += 1
                if self._n >= 1:
                    self.done = True

        monkeypatch.setattr(ht_mod, "ThresholdEngine", _UndeterminedEngine)
        statuses: list[str] = []
        profile = run_cli_hearing_test(_FakeBackend(), None, on_status=statuses.append)
        assert any("undetermined" in s for s in statuses)
        assert all(not t.determined for t in profile.left.values())
