from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import signal

from headmatch.analysis import analyze_measurement
from headmatch.io_utils import write_wav
from headmatch.peq import fit_peq, peq_chain_response_db
from headmatch.pipeline import fit_from_measurement, process_single_measurement
from headmatch.signals import SweepSpec, generate_log_sweep
from headmatch.targets import TargetCurve


def simulate_headphone_recording(tmp_path: Path):
    spec = SweepSpec(sample_rate=48000, duration_s=4.0, pre_silence_s=0.2, post_silence_s=0.5, amplitude=0.35)
    stereo, mono = generate_log_sweep(spec)
    # Build a synthetic headphone with bass boost + 3.5 kHz glare + slightly different right channel.
    fs = spec.sample_rate
    # scipy doesn't support peaking EQ directly here, so use RBJ-style biquads.
    def peaking(fc, q, gain_db):
        A = 10 ** (gain_db / 40)
        w0 = 2*np.pi*fc/fs
        alpha = np.sin(w0)/(2*q)
        c = np.cos(w0)
        b = np.array([1 + alpha*A, -2*c, 1 - alpha*A])
        a = np.array([1 + alpha/A, -2*c, 1 - alpha/A])
        return signal.tf2sos(b, a)
    left_sos = np.vstack([
        peaking(90, 0.7, 4.0),
        peaking(3500, 2.3, 5.0),
        peaking(8000, 3.0, -2.5),
    ])
    right_sos = np.vstack([
        peaking(95, 0.7, 4.5),
        peaking(3600, 2.1, 5.5),
        peaking(8200, 3.0, -2.0),
    ])
    left = signal.sosfilt(left_sos, stereo[:, 0])
    right = signal.sosfilt(right_sos, stereo[:, 1])
    # Add tiny delay and noise.
    left = np.concatenate([np.zeros(120), left[:-120]]) + 0.0002 * np.random.default_rng(0).standard_normal(len(left))
    right = np.concatenate([np.zeros(132), right[:-132]]) + 0.0002 * np.random.default_rng(1).standard_normal(len(right))
    recording = np.column_stack([left, right])
    path = tmp_path / 'recording.wav'
    write_wav(path, recording, fs)
    return path, spec


def test_measurement_and_fit(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    result = analyze_measurement(recording, spec, out_dir=tmp_path)
    assert len(result.freqs_hz) > 100
    target = TargetCurve(result.freqs_hz, np.zeros_like(result.freqs_hz), 'flat')
    left_bands, right_bands, report = fit_from_measurement(result, target, spec.sample_rate, max_filters=8)
    assert len(left_bands) >= 2
    assert len(right_bands) >= 2
    left_before = np.sqrt(np.mean(result.left_db**2))
    right_before = np.sqrt(np.mean(result.right_db**2))
    left_after = np.sqrt(np.mean((result.left_db + peq_chain_response_db(result.freqs_hz, spec.sample_rate, left_bands))**2))
    right_after = np.sqrt(np.mean((result.right_db + peq_chain_response_db(result.freqs_hz, spec.sample_rate, right_bands))**2))
    assert left_after < left_before
    assert right_after < right_before



def test_process_single_measurement_writes_run_summary(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    out_dir = tmp_path / 'fit'
    report = process_single_measurement(recording, out_dir, spec, target_path=None, max_filters=4)
    assert report['predicted_left_rms_error_db'] >= 0
    summary = (out_dir / 'run_summary.json').read_text()
    assert 'predicted_error_db' in summary
    assert (out_dir / 'camilladsp_full.yaml').exists()
    assert (out_dir / 'camilladsp_filters_only.yaml').exists()



def test_analyze_rejects_mono_recording(tmp_path: Path):
    spec = SweepSpec(sample_rate=48000, duration_s=4.0, pre_silence_s=0.2, post_silence_s=0.5, amplitude=0.35)
    mono = np.zeros((1024, 1))
    path = tmp_path / 'mono.wav'
    write_wav(path, mono, spec.sample_rate)
    try:
        analyze_measurement(path, spec, out_dir=tmp_path)
    except ValueError as exc:
        assert 'stereo' in str(exc)
    else:
        raise AssertionError('expected ValueError')
