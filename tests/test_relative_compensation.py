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


def test_edge_high_frequency_deviation_is_boosted():
    levels = _normal_shaped(-60.0)
    levels[8000] += 20.0  # worse than normal at the top edge
    points = relative_compensation_points(_side(levels))
    assert set(points) == {8000}
    assert points[8000] > 0


def test_isolated_midband_spike_is_smoothed_away():
    # A single noisy frequency surrounded by opposite-sign neighbours (like a real
    # jagged self-test) must not drive an EQ boost.
    levels = _normal_shaped(-60.0)
    levels[2000] += 16.0   # one bad point...
    levels[3000] -= 10.0   # ...with neighbours deviating the other way
    assert relative_compensation_points(_side(levels)) == {}


def test_consistent_multiband_deviation_survives_smoothing():
    # A coherent high-frequency slope (neighbours agree) should still be corrected.
    levels = {500: -60, 1000: -60, 2000: -58, 3000: -52, 4000: -46, 6000: -40, 8000: -34}
    points = relative_compensation_points(_side(levels))
    assert points and max(points) >= 6000
    assert all(g > 0 for g in points.values())


def test_gain_respects_cap():
    levels = _normal_shaped(-60.0)
    for f in (4000, 6000, 8000):
        levels[f] += 40.0  # huge, consistent HF deviation -> survives smoothing -> caps
    points = relative_compensation_points(_side(levels))
    assert points[8000] == MAX_COMPENSATION_DB


def test_reference_frequency_never_self_compensates():
    points = relative_compensation_points(_side(_normal_shaped(-55.0)))
    assert 1000 not in points


def test_lower_deadband_corrects_moderate_consistent_deviation():
    # A consistent, moderate HF slope whose per-frequency deviations all stay below
    # the old 10 dB deadband (here at most ~9 dB beyond the ISO 389-8 normal shape)
    # is now corrected with the lowered relative deadband (noise handled by smoothing).
    levels = {500: -60, 1000: -60, 2000: -58, 3000: -54, 4000: -50, 6000: -44, 8000: -41}
    assert relative_compensation_points(_side(levels))  # non-empty


def test_deviation_survives_when_intervening_frequencies_missing():
    # 2 kHz is +11 dB deviant; 3/4/6 kHz are missing (floored), so the next
    # determined frequency is 8 kHz — two octaves away. The 2 kHz deficit must NOT
    # be smoothed away by that distant point (smoothing is by log-freq distance).
    side = _side({500: -55, 1000: -60, 2000: -50, 8000: -55})
    points = relative_compensation_points(side)
    assert points.get(2000, 0) > 0


def test_too_few_determined_yields_nothing():
    side = {1000: FrequencyThreshold(1000, -60.0, 3, True)}
    assert relative_compensation_points(side) == {}
