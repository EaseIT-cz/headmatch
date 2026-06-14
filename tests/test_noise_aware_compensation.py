"""Noise-aware compensation (0.8.3 issue #3): per-point variance gate (A1),
noise-aware L/R pooling (B3), and uncertainty-weighted smoothing (C4)."""
from __future__ import annotations

from headmatch.hearing_test import (
    HearingProfile,
    FrequencyThreshold,
    NORMAL_RELATIVE_SHAPE_DB,
    TEST_FREQUENCIES,
    compute_relative_compensation,
)


def _ft(f, level, spread=1.0):
    return FrequencyThreshold(f, level, 3, True, False, spread)


def _ear(extra_and_spread: dict[int, tuple[float, float]]):
    """Normal-shaped base at -60 dBFS, with per-freq (extra_dev, spread) overrides."""
    out = {}
    for f in TEST_FREQUENCIES:
        extra, spread = extra_and_spread.get(f, (0.0, 1.0))
        out[f] = _ft(f, -60.0 + NORMAL_RELATIVE_SHAPE_DB[f] + extra, spread)
    return out


def _profile(left, right):
    return HearingProfile(left=left, right=right, tested_at="t", asymmetric_freqs=[])


# ── A1: per-point variance gate ───────────────────────────────────────────────

def test_A1_consistent_low_noise_deviation_is_corrected():
    ear = _ear({3000: (14, 1.0), 4000: (14, 1.0), 6000: (14, 1.0)})
    left, _ = compute_relative_compensation(_profile(ear, dict(ear)))
    assert any(left.get(f, 0) > 0 for f in (3000, 4000, 6000))


def test_A1_same_deviation_but_high_noise_is_gated_out():
    ear = _ear({3000: (14, 25.0), 4000: (14, 25.0), 6000: (14, 25.0)})
    left, _ = compute_relative_compensation(_profile(ear, dict(ear)))
    assert all(left.get(f, 0) == 0 for f in (3000, 4000, 6000))


# ── B3: noise-aware L/R pooling ───────────────────────────────────────────────

def test_B3_reliable_asymmetry_is_preserved_per_ear():
    left = _ear({})  # flat
    right = _ear({6000: (14, 1.0), 8000: (14, 1.0)})  # clear, low-noise HF deficit
    L, R = compute_relative_compensation(_profile(left, right))
    assert not L                                   # left untouched
    assert any(R.get(f, 0) > 0 for f in (6000, 8000))  # right corrected


def test_B3_within_noise_difference_is_pooled_symmetric():
    # L vs R differ by ~4 dB at 6/8k but both noisy enough that the difference is
    # within noise -> pooled -> the two ears get the SAME correction.
    left = _ear({6000: (5, 4.0), 8000: (5, 4.0)})
    right = _ear({6000: (9, 4.0), 8000: (9, 4.0)})
    L, R = compute_relative_compensation(_profile(left, right))
    assert L.get(6000) == R.get(6000)
    assert L.get(8000) == R.get(8000)


# ── C4: uncertainty-weighted smoothing ────────────────────────────────────────

def test_C4_reliable_point_resists_noisy_neighbours():
    # A reliable deviation at 3 kHz flanked by NOISY non-deviant neighbours should
    # keep most of its value (low-noise point dominates the weighted smoothing),
    # rather than being diluted toward the neighbours' zero.
    ear = _ear({2000: (0, 30.0), 3000: (14, 1.0), 4000: (0, 30.0)})
    left, _ = compute_relative_compensation(_profile(ear, dict(ear)))
    assert left.get(3000, 0) > 5.0  # ~half of 14; uniform smoothing would give ~3.5
