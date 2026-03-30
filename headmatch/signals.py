from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from scipy import signal


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



def inverse_sweep(reference_sweep: np.ndarray) -> np.ndarray:
    """Approximate inverse filter for Farina-style logarithmic sweep deconvolution."""
    n = len(reference_sweep)
    t = np.arange(n)
    # Exponential amplitude correction for log sweep.
    f0 = 1.0
    # Robust and simple approximation that works well enough for FR estimation.
    amp = np.exp(t / max(n - 1, 1) * np.log(1000.0))
    inv = reference_sweep[::-1] / amp
    inv /= max(np.max(np.abs(inv)), 1e-12)
    return inv.astype(np.float64)



def fractional_octave_smoothing(freqs_hz: np.ndarray, values_db: np.ndarray, fraction: float = 12.0) -> np.ndarray:
    if len(freqs_hz) != len(values_db):
        raise ValueError('freq and values must have the same length')
    out = np.empty_like(values_db)
    logf = np.log(np.maximum(freqs_hz, 1e-9))
    half_bw = np.log(2.0) / (2.0 * fraction)
    for i, lf in enumerate(logf):
        w = np.exp(-0.5 * ((logf - lf) / max(half_bw, 1e-9)) ** 2)
        w_sum = np.sum(w)
        out[i] = np.sum(w * values_db) / max(w_sum, 1e-12)
    return out



def geometric_log_grid(f_min: float = 20.0, f_max: float = 20000.0, points_per_octave: int = 48) -> np.ndarray:
    octaves = math.log2(f_max / f_min)
    points = int(octaves * points_per_octave) + 1
    return np.geomspace(f_min, f_max, points)
