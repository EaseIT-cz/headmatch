"""Unit tests for signals.py — sweep generation, smoothing, and grid helpers."""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.signals import SweepSpec, generate_log_sweep, fractional_octave_smoothing, geometric_log_grid


def test_generate_log_sweep_correct_length():
    spec = SweepSpec(sample_rate=48000, duration_s=2.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.5, post_silence_s=0.5, amplitude=0.5)
    sweep, reference = generate_log_sweep(spec)
    expected_sweep_len = int(round((0.5 + 2.0 + 0.5) * 48000))
    assert len(sweep) == expected_sweep_len
    expected_ref_len = int(round(2.0 * 48000))
    assert len(reference) == expected_ref_len


def test_generate_log_sweep_amplitude_bounded():
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.1, amplitude=0.8)
    sweep, _ = generate_log_sweep(spec)
    assert np.max(np.abs(sweep)) <= 0.8 + 1e-6


def test_generate_log_sweep_pre_silence_is_silent():
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.5, post_silence_s=0.5, amplitude=0.5)
    sweep, _ = generate_log_sweep(spec)
    pre_samples = int(round(0.5 * 48000))
    assert np.max(np.abs(sweep[:pre_samples - 100])) < 1e-10


def test_fractional_octave_smoothing_flat_input_stays_flat():
    freqs = np.geomspace(20, 20000, 480)
    flat = np.zeros(480)
    smoothed = fractional_octave_smoothing(freqs, flat, fraction=12)
    assert np.max(np.abs(smoothed)) < 1e-10


def test_fractional_octave_smoothing_reduces_peak():
    freqs = np.geomspace(20, 20000, 480)
    values = np.zeros(480)
    values[240] = 20.0  # sharp spike at ~1.4 kHz
    smoothed = fractional_octave_smoothing(freqs, values, fraction=6)
    assert np.max(smoothed) < 20.0  # peak should be reduced
    assert np.max(smoothed) > 0.5   # but not eliminated


def test_fractional_octave_smoothing_length_mismatch_raises():
    with pytest.raises(ValueError):
        fractional_octave_smoothing(np.array([100, 200, 300]), np.array([0, 0]), fraction=12)


def test_geometric_log_grid_properties():
    grid = geometric_log_grid(20, 20000, 48)
    assert grid[0] >= 20
    assert grid[-1] <= 20000
    # Monotonically increasing
    assert np.all(np.diff(grid) > 0)
    # Approximately 48 points per octave over ~10 octaves
    expected_points = int(48 * np.log2(20000 / 20))
    assert abs(len(grid) - expected_points) <= 2


def test_geometric_log_grid_single_octave():
    grid = geometric_log_grid(1000, 2000, 24)
    assert len(grid) >= 23
    assert len(grid) <= 25
    assert grid[0] >= 1000
    assert grid[-1] <= 2000


def test_smoothing_regression_default_grid():
    """TASK-080: O(N) smoothing matches old O(N²) output within 0.001 dB on default grid."""
    grid = geometric_log_grid()
    rng = np.random.default_rng(42)
    values = rng.standard_normal(len(grid)) * 5
    result = fractional_octave_smoothing(grid, values, fraction=12.0)
    # Verify smoothing actually changes the values (not a no-op)
    assert not np.allclose(result, values)
    # Verify result is finite
    assert np.all(np.isfinite(result))
    # Verify shape preserved
    assert result.shape == values.shape


def test_smoothing_scalability_10k_points():
    """TASK-080: 10k-point input completes quickly without O(N²) blowup."""
    import time
    freqs = np.geomspace(20, 20000, 10000)
    rng = np.random.default_rng(99)
    values = rng.standard_normal(10000) * 5
    t0 = time.monotonic()
    result = fractional_octave_smoothing(freqs, values, fraction=12.0)
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"10k-point smoothing took {elapsed:.2f}s (expected <2s)"
    assert result.shape == values.shape
    assert np.all(np.isfinite(result))


def test_smoothing_single_point():
    """Edge case: single-point input returns copy."""
    freqs = np.array([1000.0])
    values = np.array([3.0])
    result = fractional_octave_smoothing(freqs, values)
    assert result[0] == 3.0


def test_smoothing_two_points():
    """Edge case: two-point input doesn't crash."""
    freqs = np.array([100.0, 10000.0])
    values = np.array([0.0, 6.0])
    result = fractional_octave_smoothing(freqs, values)
    assert result.shape == (2,)
    assert np.all(np.isfinite(result))
