"""Tests for analysis.py — TASK-082: alignment robustness after find_peaks migration."""

import numpy as np
import pytest

from headmatch.analysis import _align_recording_to_reference


def _to_stereo(mono: np.ndarray) -> np.ndarray:
    """Convert 1D mono to 2D stereo (duplicate channel)."""
    return np.column_stack([mono, mono])


def _make_sweep(duration_s: float = 0.5, sr: int = 48000) -> np.ndarray:
    """Generate a simple linear chirp as a synthetic sweep reference."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return np.sin(2 * np.pi * (200 + 4000 * t) * t).astype(np.float64)


class TestAlignmentFindPeaks:
    """Verify alignment produces correct offsets with the scipy find_peaks backend."""

    def test_known_delay(self):
        """Recording with known delay should be correctly aligned."""
        sr = 48000
        sweep = _make_sweep(0.5, sr)
        delay_samples = 2400  # 50ms delay
        # Construct recording: silence + sweep + silence
        recording = np.zeros(len(sweep) + delay_samples + sr)
        recording[delay_samples:delay_samples + len(sweep)] = sweep
        aligned, diag = _align_recording_to_reference(_to_stereo(recording), sweep)
        # The aligned segment should start near the sweep
        assert len(aligned) == len(sweep)
        # Cross-correlate aligned output with sweep to verify alignment
        mono_aligned = np.mean(aligned, axis=1)
        corr = np.corrcoef(mono_aligned, sweep)[0, 1]
        assert corr > 0.9, f"Poor alignment: correlation={corr:.3f}"

    def test_known_delay_with_echo(self):
        """Recording with delay + echo should still find the primary peak."""
        sr = 48000
        sweep = _make_sweep(0.5, sr)
        delay_samples = 2400
        echo_delay = 7200  # 150ms echo
        recording = np.zeros(len(sweep) + echo_delay + sr)
        recording[delay_samples:delay_samples + len(sweep)] = sweep
        # Add echo at 0.3x amplitude
        echo_start = delay_samples + echo_delay
        echo_end = min(echo_start + len(sweep), len(recording))
        recording[echo_start:echo_end] += 0.3 * sweep[:echo_end - echo_start]
        aligned, diag = _align_recording_to_reference(_to_stereo(recording), sweep)
        assert len(aligned) == len(sweep)
        mono_aligned = np.mean(aligned, axis=1)
        corr = np.corrcoef(mono_aligned, sweep)[0, 1]
        assert corr > 0.85, f"Echo confused alignment: correlation={corr:.3f}"

    def test_noisy_recording(self):
        """Alignment should tolerate moderate noise."""
        sr = 48000
        sweep = _make_sweep(0.5, sr)
        delay_samples = 1200
        rng = np.random.default_rng(123)
        noise = rng.standard_normal(len(sweep) + delay_samples + sr) * 0.1
        recording = noise.copy()
        recording[delay_samples:delay_samples + len(sweep)] += sweep
        aligned, diag = _align_recording_to_reference(_to_stereo(recording), sweep)
        assert len(aligned) == len(sweep)
        mono_aligned = np.mean(aligned, axis=1)
        corr = np.corrcoef(mono_aligned, sweep)[0, 1]
        assert corr > 0.8, f"Noise confused alignment: correlation={corr:.3f}"
