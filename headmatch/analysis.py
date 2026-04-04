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
    diagnostics: Dict[str, float]



def _coerce_measurement_audio(data: np.ndarray, path: str | Path) -> np.ndarray:
    if data.ndim != 2:
        raise ValueError(f'{path} must be a 2D audio array')
    if len(data) == 0:
        raise ValueError(f'{path} is empty')
    if data.shape[1] == 1:
        raise ValueError(f'{path} is mono capture. Use a stereo recording with two distinct channels.')
    if data.shape[1] == 2:
        left, right = data[:, 0], data[:, 1]
        if np.allclose(left, right, rtol=1e-6, atol=1e-10):
            raise ValueError(f'{path} appears to be a duplicated-channel capture. Left and right channels are identical. Use a proper stereo recording.')
        return data[:, :2]
    if data.shape[1] >= 2:
        return data[:, :2]
    raise ValueError(f'{path} must contain at least one channel')



def _alignment_reference_score(segment: np.ndarray, reference: np.ndarray) -> float:
    segment = segment - np.mean(segment)
    reference = reference - np.mean(reference)
    denom = np.linalg.norm(segment) * np.linalg.norm(reference)
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(segment, reference) / denom)



def _align_recording_to_reference(recording: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    mono_rec = np.mean(recording, axis=1)
    mono_rec = mono_rec - np.mean(mono_rec)
    ref = reference - np.mean(reference)
    energy = np.abs(ref)
    gate = energy >= (0.12 * np.max(energy))
    corr = signal.fftconvolve(mono_rec, ref[::-1], mode='full')
    candidate_offsets = np.argsort(np.abs(corr))[-8:]
    candidate_offsets = np.unique(candidate_offsets - len(reference) + 1)

    best_offset = 0
    best_score = float('-inf')
    best_peak = 0.0
    corr_abs = np.abs(corr)
    corr_max = float(np.max(corr_abs)) if len(corr_abs) else 0.0
    for raw_offset in candidate_offsets:
        offset = int(raw_offset)
        start = max(offset, 0)
        end = min(offset + len(reference), len(recording))
        segment = np.zeros(len(reference), dtype=np.float64)
        if end > start:
            seg_start = max(-offset, 0)
            segment[seg_start:seg_start + (end - start)] = mono_rec[start:end]
        score = _alignment_reference_score(segment[gate], ref[gate])
        peak_index = int(offset + len(reference) - 1)
        peak = float(corr_abs[peak_index]) if 0 <= peak_index < len(corr_abs) else 0.0
        if score > best_score:
            best_score = score
            best_offset = offset
            best_peak = peak

    offset = best_offset
    truncated_head = 0
    if offset < 0:
        truncated_head = -offset
        recording = recording[-offset:]
        offset = 0
    end = offset + len(reference)
    truncated_tail = max(end - len(recording), 0)
    if end > len(recording):
        padded = np.zeros((len(reference), recording.shape[1]))
        avail = max(len(recording) - offset, 0)
        if avail > 0:
            padded[:avail] = recording[offset:offset + avail]
        return padded, {
            'alignment_offset_samples': float(best_offset),
            'alignment_reference_score': float(best_score),
            'alignment_peak_ratio': float(best_peak / corr_max) if corr_max > 1e-12 else 0.0,
            'alignment_head_trimmed_samples': float(truncated_head),
            'alignment_tail_padded_samples': float(truncated_tail),
        }
    return recording[offset:end], {
        'alignment_offset_samples': float(best_offset),
        'alignment_reference_score': float(best_score),
        'alignment_peak_ratio': float(best_peak / corr_max) if corr_max > 1e-12 else 0.0,
        'alignment_head_trimmed_samples': float(truncated_head),
        'alignment_tail_padded_samples': 0.0,
    }



def _fr_from_signals(reference: np.ndarray, response: np.ndarray, sample_rate: int, f_min=20.0, f_max=20000.0) -> tuple[np.ndarray, np.ndarray]:
    nfft = int(2 ** np.ceil(np.log2(max(len(reference), len(response)))))
    ref_fft = np.fft.rfft(reference, n=nfft)
    resp_fft = np.fft.rfft(response, n=nfft)
    h = resp_fft / np.where(np.abs(ref_fft) > 1e-12, ref_fft, 1e-12)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
    mask = (freqs >= f_min) & (freqs <= f_max)
    return freqs[mask], 20 * np.log10(np.maximum(np.abs(h[mask]), 1e-12))



def _band_mask(freqs_hz: np.ndarray, low_hz: float = 80.0, high_hz: float = 8000.0) -> np.ndarray:
    return (freqs_hz >= low_hz) & (freqs_hz <= high_hz)



def _roughness_db(raw_db: np.ndarray, smoothed_db: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.sqrt(np.mean((raw_db[mask] - smoothed_db[mask]) ** 2)))



def _channel_mismatch_db(left_db: np.ndarray, right_db: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.sqrt(np.mean((left_db[mask] - right_db[mask]) ** 2)))



def analyze_measurement(recording_wav: str | Path, sweep_spec: SweepSpec, out_dir: str | Path | None = None) -> MeasurementResult:
    recording, sr = read_wav(recording_wav)
    recording = _coerce_measurement_audio(recording, recording_wav)
    if sr != sweep_spec.sample_rate:
        raise ValueError(f'Sample rate mismatch: recording {sr}, expected {sweep_spec.sample_rate}')
    min_len = int(round((sweep_spec.pre_silence_s + sweep_spec.duration_s * 0.5) * sweep_spec.sample_rate))
    if len(recording) < min_len:
        raise ValueError(f'Recording too short: {len(recording)} samples; expected at least {min_len}')
    from .signals import generate_log_sweep
    _, reference = generate_log_sweep(sweep_spec)
    padded_len = int(round((sweep_spec.pre_silence_s + sweep_spec.duration_s + sweep_spec.post_silence_s) * sweep_spec.sample_rate))
    padded = np.zeros(padded_len)
    start = int(round(sweep_spec.pre_silence_s * sweep_spec.sample_rate))
    padded[start:start + len(reference)] = reference
    aligned, alignment_diagnostics = _align_recording_to_reference(recording, padded)
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

    mask = _band_mask(grid)
    diagnostics = {
        **alignment_diagnostics,
        'left_roughness_db': _roughness_db(left_norm, left_s, mask),
        'right_roughness_db': _roughness_db(right_norm, right_s, mask),
        'channel_mismatch_rms_db': _channel_mismatch_db(left_s, right_s, mask),
        'capture_rms_dbfs': float(20 * np.log10(max(np.sqrt(np.mean(aligned ** 2)), 1e-12))),
    }

    result = MeasurementResult(
        freqs_hz=grid,
        left_db=left_s,
        right_db=right_s,
        left_raw_db=left_norm,
        right_raw_db=right_norm,
        diagnostics=diagnostics,
    )
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_fr_csv(out_dir / 'measurement_left.csv', result.freqs_hz, result.left_db)
        save_fr_csv(out_dir / 'measurement_right.csv', result.freqs_hz, result.right_db)
        save_fr_csv(out_dir / 'measurement_left_raw.csv', result.freqs_hz, result.left_raw_db)
        save_fr_csv(out_dir / 'measurement_right_raw.csv', result.freqs_hz, result.right_raw_db)
    return result
