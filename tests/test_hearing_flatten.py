"""Tests for the opt-in 'flatten' knob: how much of the natural ISO-normal rolloff
to also correct (0 = compensate-to-normal, 1 = full flatten-to-1k).

    dev(f) = (threshold(f) - threshold_1k) - (1 - flatten) * NORMAL_RELATIVE_SHAPE_DB[f]
"""
from __future__ import annotations

import json

from headmatch.hearing_test import (
    NORMAL_RELATIVE_SHAPE_DB,
    FrequencyThreshold,
    HearingProfile,
    compute_relative_compensation,
    relative_compensation_points,
)


def _side(levels: dict[int, float]) -> dict[int, FrequencyThreshold]:
    return {f: FrequencyThreshold(f, levels[f], 3, True) for f in levels}


def _normal_shaped(base: float) -> dict[int, float]:
    # A listener whose threshold shape == the ISO-normal shape: zero deviation at
    # flatten=0, so the natural rolloff itself is what flatten>0 starts correcting.
    return {f: base + NORMAL_RELATIVE_SHAPE_DB[f]
            for f in (250, 500, 1000, 2000, 3000, 4000, 6000, 8000)}


class TestFlattenKnob:
    def test_default_is_compensate_to_normal(self):
        # flatten defaults to 0 -> a normal-shaped listener needs no correction.
        assert relative_compensation_points(_side(_normal_shaped(-60.0))) == {}

    def test_flatten_zero_explicit_matches_default(self):
        side = _side(_normal_shaped(-60.0))
        assert relative_compensation_points(side, flatten=0.0) == {}

    def test_full_flatten_corrects_natural_rolloff(self):
        # At flatten=1 the natural HF rolloff (and bass) becomes a deviation to lift.
        pts = relative_compensation_points(_side(_normal_shaped(-60.0)), flatten=1.0)
        assert pts, "full flatten should produce boosts for a normal-shaped listener"
        assert max(pts) >= 8000  # the air band is lifted

    def test_partial_flatten_between_none_and_full(self):
        side = _side(_normal_shaped(-60.0))
        half = relative_compensation_points(side, flatten=0.5)
        full = relative_compensation_points(side, flatten=1.0)
        # Half-flatten lifts the top less than full-flatten.
        assert sum(half.values()) < sum(full.values())

    def test_flatten_is_clamped(self):
        side = _side(_normal_shaped(-60.0))
        assert relative_compensation_points(side, flatten=5.0) == \
               relative_compensation_points(side, flatten=1.0)
        assert relative_compensation_points(side, flatten=-3.0) == \
               relative_compensation_points(side, flatten=0.0)

    def test_flatten_is_hf_only_never_boosts_bass(self):
        # A normal-shaped listener has normal bass; flatten must not boost 250/500
        # Hz at ANY strength (air-band shaping leaves bass on compensate-to-normal).
        side = _side(_normal_shaped(-60.0))
        for fl in (0.35, 0.6, 1.0):
            pts = relative_compensation_points(side, flatten=fl)
            assert 250 not in pts and 500 not in pts, (fl, pts)
        # At full flatten the air band IS lifted (just not the bass).
        assert any(f >= 8000 for f in relative_compensation_points(side, flatten=1.0))


class TestFlattenOnRealProfile:
    def _profile(self):
        return HearingProfile.from_dict(json.loads(_REAL_PROFILE))

    def test_flatten_zero_recovers_edge_only(self):
        l, r = compute_relative_compensation(self._profile(), flatten=0.0)
        assert set(l) == {12500}  # compensate-to-normal: just the EHF cliff

    def test_flatten_lifts_air_band(self):
        l, _ = compute_relative_compensation(self._profile(), flatten=1.0)
        # Air-band frequencies above 8 kHz get lifted at full flatten.
        assert any(f >= 10000 for f in l)
        assert sum(l.values()) > 0


# The reporter's real profile (abridged to determined frequencies).
_REAL_PROFILE = json.dumps({
    "tested_at": "t", "asymmetric_freqs": [],
    "left": {
        "250": {"freq_hz": 250, "level_dbfs": -40.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "500": {"freq_hz": 500, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "1000": {"freq_hz": 1000, "level_dbfs": -52.5, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.5},
        "2000": {"freq_hz": 2000, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "3000": {"freq_hz": 3000, "level_dbfs": -55.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "4000": {"freq_hz": 4000, "level_dbfs": -61.67, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.36},
        "6000": {"freq_hz": 6000, "level_dbfs": -46.67, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.36},
        "8000": {"freq_hz": 8000, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "10000": {"freq_hz": 10000, "level_dbfs": -40.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "12500": {"freq_hz": 12500, "level_dbfs": -15.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "16000": {"freq_hz": 16000, "level_dbfs": None, "ascending_runs": 0, "determined": False, "floored": False, "spread_db": 0.0},
    },
    "right": {
        "250": {"freq_hz": 250, "level_dbfs": -42.5, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.5},
        "500": {"freq_hz": 500, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "1000": {"freq_hz": 1000, "level_dbfs": -52.5, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.5},
        "2000": {"freq_hz": 2000, "level_dbfs": -46.67, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 2.36},
        "3000": {"freq_hz": 3000, "level_dbfs": -60.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "4000": {"freq_hz": 4000, "level_dbfs": -55.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "6000": {"freq_hz": 6000, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "8000": {"freq_hz": 8000, "level_dbfs": -50.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "10000": {"freq_hz": 10000, "level_dbfs": -45.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "12500": {"freq_hz": 12500, "level_dbfs": -25.0, "ascending_runs": 3, "determined": True, "floored": False, "spread_db": 0.0},
        "16000": {"freq_hz": 16000, "level_dbfs": None, "ascending_runs": 0, "determined": False, "floored": False, "spread_db": 0.0},
    },
})
