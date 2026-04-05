from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d


@dataclass
class SweepSpec:
    sample_rate: int = 48000
    duration_s: float = 8.0
    f_start: float = 20.0
    f_end: float = 22000.0
    pre_silence_s: float = 0.5
    post_silence_s: float = 1.0
    amplitude: float = 0.2
    channel: str = 'both'  # left, right, both



def generate_log_sweep(spec: SweepSpec) -> Tuple[np.ndarray, np.ndarray]:
    """Returns stereo sweep and mono reference sweep."""
    n = int(round(spec.duration_s * spec.sample_rate))
    t = np.linspace(0.0, spec.duration_s, n, endpoint=False)
    mono = signal.chirp(
        t,
        f0=spec.f_start,
        t1=spec.duration_s,
        f1=spec.f_end,
        method='logarithmic',
        phi=-90,
    ).astype(np.float64)

    # Cosine fade to reduce clicks
    fade_len = min(int(0.02 * spec.sample_rate), len(mono) // 10)
    if fade_len > 1:
        fade = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade_len))
        mono[:fade_len] *= fade
        mono[-fade_len:] *= fade[::-1]

    mono *= spec.amplitude

    pre = np.zeros(int(round(spec.pre_silence_s * spec.sample_rate)))
    post = np.zeros(int(round(spec.post_silence_s * spec.sample_rate)))
    mono_with_padding = np.concatenate([pre, mono, post])
    stereo = np.zeros((len(mono_with_padding), 2), dtype=np.float64)
    if spec.channel in ('left', 'both'):
        stereo[:, 0] = mono_with_padding
    if spec.channel in ('right', 'both'):
        stereo[:, 1] = mono_with_padding
    return stereo, mono



def fractional_octave_smoothing(freqs_hz: np.ndarray, values_db: np.ndarray, fraction: float = 12.0) -> np.ndarray:
    """Fractional-octave Gaussian smoothing in log-frequency domain.

    Uses a uniform log2-frequency grid with scipy gaussian_filter1d for O(N)
    time and memory, instead of the previous O(N²) weight-matrix approach.
    Edge handling replicates the truncated-kernel normalization of the original
    by dividing smoothed values by smoothed ones (constant zero padding).
    """
    if len(freqs_hz) != len(values_db):
        raise ValueError('freq and values must have the same length')
    if len(freqs_hz) < 2:
        return values_db.copy()
    logf = np.log2(np.maximum(freqs_hz, 1e-9))
    # Resample onto a uniform log2-frequency grid
    n = len(logf)
    grid = np.linspace(logf[0], logf[-1], n)
    v_uniform = np.interp(grid, logf, values_db)
    # Sigma in octaves ≈ 1/(2*fraction), converted to grid samples
    sigma_oct = 1.0 / (2.0 * max(fraction, 1e-9))
    step = (grid[-1] - grid[0]) / max(n - 1, 1)
    sigma_samples = sigma_oct / max(step, 1e-12)
    # Normalized smoothing: smooth(values)/smooth(ones) replicates the
    # truncated-kernel edge behavior of the original NxN approach.
    numerator = gaussian_filter1d(v_uniform, sigma_samples, mode="constant", cval=0.0)
    denominator = gaussian_filter1d(np.ones(n), sigma_samples, mode="constant", cval=0.0)
    v_smoothed = np.where(denominator > 1e-12, numerator / denominator, v_uniform)
    # Interpolate back to original (possibly non-uniform) frequency points
    return np.interp(logf, grid, v_smoothed)



def geometric_log_grid(f_min: float = 20.0, f_max: float = 20000.0, points_per_octave: int = 48) -> np.ndarray:
    octaves = math.log2(f_max / f_min)
    points = int(octaves * points_per_octave) + 1
    return np.geomspace(f_min, f_max, points)
