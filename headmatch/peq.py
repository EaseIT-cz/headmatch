from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List

import numpy as np
from scipy import signal

from .signals import fractional_octave_smoothing


@dataclass
class PEQBand:
    kind: str  # peaking, lowshelf, highshelf
    freq: float
    gain_db: float
    q: float



def biquad_response_db(freqs_hz: np.ndarray, fs: int, band: PEQBand) -> np.ndarray:
    w0 = 2 * np.pi * band.freq / fs
    A = 10 ** (band.gain_db / 40)
    alpha = np.sin(w0) / (2 * max(band.q, 1e-6))
    cosw = np.cos(w0)

    if band.kind == 'peaking':
        b0 = 1 + alpha * A
        b1 = -2 * cosw
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cosw
        a2 = 1 - alpha / A
    elif band.kind == 'lowshelf':
        sqrtA = np.sqrt(A)
        # RBJ shelf. Here q is used as slope-ish control via S=q.
        S = max(0.1, min(1.0, band.q))
        alpha = np.sin(w0) / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
        b0 = A * ((A + 1) - (A - 1) * cosw + 2 * sqrtA * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cosw)
        b2 = A * ((A + 1) - (A - 1) * cosw - 2 * sqrtA * alpha)
        a0 = (A + 1) + (A - 1) * cosw + 2 * sqrtA * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cosw)
        a2 = (A + 1) + (A - 1) * cosw - 2 * sqrtA * alpha
    elif band.kind == 'highshelf':
        sqrtA = np.sqrt(A)
        S = max(0.1, min(1.0, band.q))
        alpha = np.sin(w0) / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
        b0 = A * ((A + 1) + (A - 1) * cosw + 2 * sqrtA * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cosw)
        b2 = A * ((A + 1) + (A - 1) * cosw - 2 * sqrtA * alpha)
        a0 = (A + 1) - (A - 1) * cosw + 2 * sqrtA * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cosw)
        a2 = (A + 1) - (A - 1) * cosw - 2 * sqrtA * alpha
    else:
        raise ValueError(f'Unsupported band type: {band.kind}')

    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    _, h = signal.freqz(b, a, worN=2 * np.pi * freqs_hz / fs)
    return 20 * np.log10(np.maximum(np.abs(h), 1e-12))



def peq_chain_response_db(freqs_hz: np.ndarray, fs: int, bands: List[PEQBand]) -> np.ndarray:
    total = np.zeros_like(freqs_hz)
    for band in bands:
        total += biquad_response_db(freqs_hz, fs, band)
    return total



def _residual_priority_weights(freqs_hz: np.ndarray) -> np.ndarray:
    weights = np.ones_like(freqs_hz)
    weights[(freqs_hz >= 60) & (freqs_hz <= 10000)] = 1.5
    weights[(freqs_hz >= 2000) & (freqs_hz <= 8000)] = 2.0
    weights[freqs_hz > 12000] = 0.35
    return weights



def fit_peq(
    freqs_hz: np.ndarray,
    target_eq_db: np.ndarray,
    sample_rate: int,
    max_filters: int = 8,
    max_gain_db: float = 8.0,
    max_q: float = 4.5,
) -> List[PEQBand]:
    """Greedy PEQ fitter. Good enough for practical headphone work, intentionally conservative."""
    eq_target = fractional_octave_smoothing(freqs_hz, target_eq_db, fraction=8)
    bands: List[PEQBand] = []
    weights = _residual_priority_weights(freqs_hz)

    # Broad shelves first.
    bass_mask = freqs_hz <= 120
    treble_mask = freqs_hz >= 6000
    bass_mean = float(np.mean(eq_target[bass_mask])) if np.any(bass_mask) else 0.0
    treble_mean = float(np.mean(eq_target[treble_mask])) if np.any(treble_mask) else 0.0
    if abs(bass_mean) > 1.0:
        bands.append(PEQBand('lowshelf', 105.0, float(np.clip(bass_mean, -max_gain_db, max_gain_db)), 0.7))
    if abs(treble_mean) > 1.0:
        bands.append(PEQBand('highshelf', 8500.0, float(np.clip(treble_mean, -max_gain_db, max_gain_db)), 0.7))

    for _ in range(max_filters - len(bands)):
        current = peq_chain_response_db(freqs_hz, sample_rate, bands)
        residual = eq_target - current
        residual = fractional_octave_smoothing(freqs_hz, residual, fraction=10)
        weighted = residual * weights
        idx = int(np.argmax(np.abs(weighted)))
        peak_db = float(weighted[idx] / weights[idx])
        if abs(peak_db) < 0.75:
            break
        fc = float(freqs_hz[idx])

        # Estimate width from contiguous region above half height.
        threshold = abs(peak_db) * 0.5
        l = idx
        while l > 0 and abs(residual[l]) >= threshold:
            l -= 1
        r = idx
        while r < len(freqs_hz) - 1 and abs(residual[r]) >= threshold:
            r += 1
        f1, f2 = max(freqs_hz[l], 20.0), min(freqs_hz[r], sample_rate / 2 - 100)
        bw_oct = max(np.log2(f2 / f1), 0.12)
        q = float(np.clip(1.0 / bw_oct, 0.4, max_q))
        gain = float(np.clip(peak_db, -max_gain_db, max_gain_db))
        bands.append(PEQBand('peaking', fc, gain, q))

    return bands
