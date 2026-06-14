"""Part B core (0.8.3): relative, calibration-invariant hearing compensation.

Each ear's thresholds are referenced to its own 1 kHz threshold, the normal
threshold shape (ISO 389-8 RETSPL, relative to 1 kHz) is subtracted to isolate
the listener's deviation, and a fractional/deadbanded/capped gain results.
"""
from __future__ import annotations

from headmatch.hearing_test import (
    FrequencyThreshold,
    MAX_COMPENSATION_DB,
    NORMAL_RELATIVE_SHAPE_DB,
    TEST_FREQUENCIES,
    relative_compensation_points,
)


def _side(levels: dict[int, float]) -> dict[int, FrequencyThreshold]:
    return {f: FrequencyThreshold(f, levels[f], 3, True) for f in levels}


def _normal_shaped(base_dbfs: float) -> dict[int, float]:
    # A listener whose relative threshold shape equals the normal shape -> no deviation.
    return {f: base_dbfs + NORMAL_RELATIVE_SHAPE_DB[f] for f in TEST_FREQUENCIES}


def test_normal_shaped_listener_gets_no_compensation():
    side = _side(_normal_shaped(-60.0))
    assert relative_compensation_points(side) == {}


def test_calibration_invariance_to_overall_volume():
    # Shifting every threshold by a constant (a volume change) must not change the EQ.
    levels = _normal_shaped(-60.0)
    levels[8000] += 20.0  # high-frequency deviation
    quiet = relative_compensation_points(_side(levels))
    loud = relative_compensation_points(_side({f: v + 25.0 for f, v in levels.items()}))
    assert quiet == loud
    assert quiet  # and it actually produced a correction


def test_high_frequency_deviation_boosts_only_that_region():
    levels = _normal_shaped(-60.0)
    levels[8000] += 20.0  # 20 dB worse than normal at 8 kHz, relative to own 1 kHz
    points = relative_compensation_points(side := _side(levels))
    assert set(points) == {8000}
    # Half-gain of the 20 dB deviation, capped at 12.
    assert points[8000] == 10.0


def test_gain_respects_cap():
    levels = _normal_shaped(-60.0)
    levels[8000] += 40.0  # huge deviation
    points = relative_compensation_points(_side(levels))
    assert points[8000] == MAX_COMPENSATION_DB


def test_reference_frequency_never_self_compensates():
    points = relative_compensation_points(_side(_normal_shaped(-55.0)))
    assert 1000 not in points


def test_too_few_determined_yields_nothing():
    side = {1000: FrequencyThreshold(1000, -60.0, 3, True)}
    assert relative_compensation_points(side) == {}
