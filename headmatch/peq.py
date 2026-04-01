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



def _band_mean(freqs_hz: np.ndarray, values_db: np.ndarray, low_hz: float, high_hz: float) -> float:
    mask = (freqs_hz >= low_hz) & (freqs_hz <= high_hz)
    if not np.any(mask):
        return 0.0
    return float(np.mean(values_db[mask]))



def _same_sign_fraction(values: np.ndarray, sign: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.mean(np.sign(values) == np.sign(sign)))



def _maybe_add_edge_shelf(bands: List[PEQBand], freqs_hz: np.ndarray, eq_target: np.ndarray, *, kind: str, max_gain_db: float) -> None:
    if kind == 'lowshelf':
        edge_mask = freqs_hz <= 140
        compare_mean = _band_mean(freqs_hz, eq_target, 180, 600)
        edge_mean = _band_mean(freqs_hz, eq_target, 20, 140)
        freq = 105.0
    else:
        edge_mask = freqs_hz >= 7000
        compare_mean = _band_mean(freqs_hz, eq_target, 2500, 5500)
        edge_mean = _band_mean(freqs_hz, eq_target, 7000, min(float(freqs_hz[-1]), 16000.0))
        freq = 8500.0

    if not np.any(edge_mask):
        return
    edge_values = eq_target[edge_mask]
    if abs(edge_mean) < 1.25:
        return
    if abs(edge_mean - compare_mean) < 0.75:
        return
    if _same_sign_fraction(edge_values, edge_mean) < 0.7:
        return
    bands.append(PEQBand(kind, freq, float(np.clip(edge_mean, -max_gain_db, max_gain_db)), 0.7))



def _max_q_for_frequency(freq_hz: float, requested_max_q: float) -> float:
    if freq_hz < 120:
        return min(requested_max_q, 2.0)
    if freq_hz > 6000:
        return min(requested_max_q, 3.0)
    return requested_max_q



def _nearby_same_sign_band_exists(bands: List[PEQBand], candidate: PEQBand) -> bool:
    for band in bands:
        if band.kind != candidate.kind:
            continue
        if np.sign(band.gain_db) != np.sign(candidate.gain_db):
            continue
        if abs(np.log2(max(band.freq, 1.0) / max(candidate.freq, 1.0))) < 0.2:
            return True
    return False



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

    _maybe_add_edge_shelf(bands, freqs_hz, eq_target, kind='lowshelf', max_gain_db=max_gain_db)
    _maybe_add_edge_shelf(bands, freqs_hz, eq_target, kind='highshelf', max_gain_db=max_gain_db)

    for _ in range(max_filters - len(bands)):
        current = peq_chain_response_db(freqs_hz, sample_rate, bands)
        residual = eq_target - current
        residual = fractional_octave_smoothing(freqs_hz, residual, fraction=10)
        weighted = residual * weights
        idx = int(np.argmax(np.abs(weighted)))
        peak_db = float(weighted[idx] / weights[idx])
        if abs(peak_db) < 0.75:
            break
        fc = float(np.clip(freqs_hz[idx], 35.0, sample_rate / 2 - 500.0))

        threshold = abs(peak_db) * 0.5
        l = idx
        while l > 0 and abs(residual[l]) >= threshold:
            l -= 1
        r = idx
        while r < len(freqs_hz) - 1 and abs(residual[r]) >= threshold:
            r += 1
        f1, f2 = max(freqs_hz[l], 20.0), min(freqs_hz[r], sample_rate / 2 - 100)
        bw_oct = max(np.log2(f2 / f1), 0.12)
        q_limit = _max_q_for_frequency(fc, max_q)
        q = float(np.clip(1.0 / bw_oct, 0.45, q_limit))
        gain = float(np.clip(peak_db, -max_gain_db, max_gain_db))
        if q >= 2.8:
            gain *= 0.85
        candidate = PEQBand('peaking', fc, gain, q)
        if abs(candidate.gain_db) < 0.6:
            break
        if _nearby_same_sign_band_exists(bands, candidate):
            continue
        bands.append(candidate)

    return bands
