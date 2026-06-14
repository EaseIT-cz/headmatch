"""Regression: a real deviation at the *highest determined* frequency must not be
smoothed away just because the frequency above it is undetermined and its lower
neighbours deviate the other way.

Root cause (see debugging session 2026-06-14): the cross-frequency smoothing in
``_smooth_and_gate`` treated a top-edge deviation as an isolated noise spike,
dragging a +15.5 dB excess at 12.5 kHz down to ~2 dB and gating it out — so a
listener with a genuine EHF rolloff got an empty preset.
"""
from __future__ import annotations

from headmatch.hearing_test import (
    FrequencyThreshold,
    HearingProfile,
    NORMAL_RELATIVE_SHAPE_DB,
    relative_compensation_points,
)


def _side(levels: dict[int, float], undetermined: tuple[int, ...] = ()) -> dict[int, FrequencyThreshold]:
    side = {f: FrequencyThreshold(f, levels[f], 3, True) for f in levels}
    for f in undetermined:
        side[f] = FrequencyThreshold(f, None, 0, False)
    return side


# The reporter's actual left ear: better-than-normal across the mid/HF, a steep
# rolloff to a large +15.5 dB excess at 12.5 kHz, and 16 kHz undetermined.
_LEFT_LEVELS = {
    250: -40.0, 500: -50.0, 1000: -52.5, 2000: -50.0, 3000: -55.0,
    4000: -61.67, 6000: -46.67, 8000: -50.0, 10000: -40.0, 12500: -15.0,
}


def test_top_edge_deviation_survives_smoothing():
    side = _side(_LEFT_LEVELS, undetermined=(16000,))
    points = relative_compensation_points(side)
    assert 12500 in points, "top-edge EHF deviation was smoothed away"
    assert points[12500] > 0


def test_interior_isolated_spike_still_rejected():
    # Guard against over-correcting: a lone spike flanked by opposite-sign
    # neighbours on BOTH sides is still treated as noise and produces no boost.
    levels = {f: -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] for f in (500, 1000, 2000, 3000, 4000, 6000)}
    levels[3000] += 16.0   # lone interior spike up...
    levels[2000] -= 8.0
    levels[4000] -= 8.0    # ...flanked by opposite-sign neighbours both sides
    points = relative_compensation_points(_side(levels))
    assert 3000 not in points
