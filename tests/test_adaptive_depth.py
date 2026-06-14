"""Adaptive measurement depth (0.8.3): 1 pass per frequency, repeat only deviant
ones (and >=2 for the reference) — fast on clean ears, careful where it matters."""
from __future__ import annotations

from headmatch.hearing_test import (
    MEASUREMENT_REPEATS,
    NORMAL_RELATIVE_SHAPE_DB,
    adaptive_needs_more_passes,
)


def test_always_does_at_least_min_passes():
    assert adaptive_needs_more_passes(2000, [], None, 0, min_passes=1) is True
    assert adaptive_needs_more_passes(1000, [-60.0], -60.0, 1, min_passes=2) is True  # reference anchor


def test_never_exceeds_max_passes():
    assert adaptive_needs_more_passes(2000, [-50.0], -55.0, MEASUREMENT_REPEATS, min_passes=1) is False


def test_non_deviant_frequency_stops_after_one_pass():
    ref = -55.0
    level = ref - NORMAL_RELATIVE_SHAPE_DB[2000]  # exactly normal-shaped -> dev 0
    assert adaptive_needs_more_passes(2000, [level], ref, 1, min_passes=1) is False


def test_deviant_frequency_is_repeated():
    ref = -55.0
    level = ref + 14.0  # 14 dB louder than reference at 2 kHz -> candidate
    assert adaptive_needs_more_passes(2000, [level], ref, 1, min_passes=1) is True


def test_no_reference_yet_stops_after_min():
    assert adaptive_needs_more_passes(2000, [-50.0], None, 1, min_passes=1) is False
