from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import numpy as np
from scipy import signal

from .io_utils import read_wav, save_fr_csv
from .signals import SweepSpec, fractional_octave_smoothing, geometric_log_grid


@dataclass
class MeasurementResult:
    freqs_hz: np.ndarray
    left_db: np.ndarray
    right_db: np.ndarray
    left_raw_db: np.ndarray
    right_raw_db: np.ndarray



def _align_recording_to_reference(recording: np.ndarray, reference: np.ndarray) -> np.ndarray:
    mono_rec = np.mean(recording, axis=1)
    corr = signal.fftconvolve(mono_rec, reference[::-1], mode='full')
    offset = int(np.argmax(np.abs(corr)) - len(reference) + 1)
    if offset < 0:
        recording = recording[-offset:]
        offset = 0
    end = offset + len(reference)
    if end > len(recording):
        padded = np.zeros((len(reference), recording.shape[1]))
        avail = max(len(recording) - offset, 0)
        if avail > 0:
            padded[:avail] = recording[offset:offset + avail]
        return padded
    return recording[offset:end]



def _fr_from_signals(reference: np.ndarray, response: np.ndarray, sample_rate: int, f_min=20.0, f_max=20000.0) -> tuple[np.ndarray, np.ndarray]:
    nfft = int(2 ** np.ceil(np.log2(max(len(reference), len(response)))))
    ref_fft = np.fft.rfft(reference, n=nfft)
    resp_fft = np.fft.rfft(response, n=nfft)
    h = resp_fft / np.maximum(ref_fft, 1e-12)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
    mask = (freqs >= f_min) & (freqs <= f_max)
    return freqs[mask], 20 * np.log10(np.maximum(np.abs(h[mask]), 1e-12))



def analyze_measurement(recording_wav: str | Path, sweep_spec: SweepSpec, out_dir: str | Path | None = None) -> MeasurementResult:
    recording, sr = read_wav(recording_wav)
    if sr != sweep_spec.sample_rate:
        raise ValueError(f'Sample rate mismatch: recording {sr}, expected {sweep_spec.sample_rate}')
    from .signals import generate_log_sweep
    _, reference = generate_log_sweep(sweep_spec)
    # extract the padded sweep actually played on one channel
    padded_len = int(round((sweep_spec.pre_silence_s + sweep_spec.duration_s + sweep_spec.post_silence_s) * sweep_spec.sample_rate))
    padded = np.zeros(padded_len)
    start = int(round(sweep_spec.pre_silence_s * sweep_spec.sample_rate))
    padded[start:start + len(reference)] = reference
    aligned = _align_recording_to_reference(recording, padded)
    left = aligned[:, 0]
    right = aligned[:, 1]

    freqs_l, left_raw = _fr_from_signals(padded, left, sr)
    freqs_r, right_raw = _fr_from_signals(padded, right, sr)
    grid = geometric_log_grid(20, min(20000, sr / 2 - 1), 48)
    left_interp = np.interp(grid, freqs_l, left_raw)
    right_interp = np.interp(grid, freqs_r, right_raw)
    left_norm = left_interp - np.interp(1000.0, grid, left_interp)
    right_norm = right_interp - np.interp(1000.0, grid, right_interp)
    left_s = fractional_octave_smoothing(grid, left_norm, fraction=12)
    right_s = fractional_octave_smoothing(grid, right_norm, fraction=12)
    result = MeasurementResult(
        freqs_hz=grid,
        left_db=left_s,
        right_db=right_s,
        left_raw_db=left_norm,
        right_raw_db=right_norm,
    )
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_fr_csv(out_dir / 'measurement_left.csv', result.freqs_hz, result.left_db)
        save_fr_csv(out_dir / 'measurement_right.csv', result.freqs_hz, result.right_db)
        save_fr_csv(out_dir / 'measurement_left_raw.csv', result.freqs_hz, result.left_raw_db)
        save_fr_csv(out_dir / 'measurement_right_raw.csv', result.freqs_hz, result.right_raw_db)
    return result
