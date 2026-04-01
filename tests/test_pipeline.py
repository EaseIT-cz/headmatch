from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from headmatch.analysis import analyze_measurement
from headmatch.io_utils import write_wav
from headmatch.peq import peq_chain_response_db
from headmatch.pipeline import fit_from_measurement, iterative_measure_and_fit, process_single_measurement
from headmatch.signals import SweepSpec, generate_log_sweep
from headmatch.targets import TargetCurve


def simulate_headphone_recording(
    tmp_path: Path,
    *,
    left_delay: int = 120,
    right_delay: int = 132,
    noise_scale: float = 0.0002,
    right_gain: float = 1.0,
    extra_lead_in_s: float = 0.0,
):
    spec = SweepSpec(sample_rate=48000, duration_s=4.0, pre_silence_s=0.2, post_silence_s=0.5, amplitude=0.35)
    stereo, _ = generate_log_sweep(spec)
    fs = spec.sample_rate

    def peaking(fc, q, gain_db):
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * fc / fs
        alpha = np.sin(w0) / (2 * q)
        c = np.cos(w0)
        b = np.array([1 + alpha * A, -2 * c, 1 - alpha * A])
        a = np.array([1 + alpha / A, -2 * c, 1 - alpha / A])
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
    right = signal.sosfilt(right_sos, stereo[:, 1]) * right_gain
    left = np.concatenate([np.zeros(left_delay), left[:-left_delay]]) + noise_scale * np.random.default_rng(0).standard_normal(len(left))
    right = np.concatenate([np.zeros(right_delay), right[:-right_delay]]) + noise_scale * np.random.default_rng(1).standard_normal(len(right))
    recording = np.column_stack([left, right])
    if extra_lead_in_s > 0:
        lead = np.zeros((int(round(extra_lead_in_s * fs)), 2))
        recording = np.vstack([lead, recording])
    path = tmp_path / 'recording.wav'
    write_wav(path, recording, fs)
    return path, spec


def test_measurement_and_fit(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    result = analyze_measurement(recording, spec, out_dir=tmp_path)
    assert len(result.freqs_hz) > 100
    target = TargetCurve(result.freqs_hz, np.zeros_like(result.freqs_hz), 'flat')
    left_bands, right_bands, _report = fit_from_measurement(result, target, spec.sample_rate, max_filters=8)
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
    assert 'generated_by' in summary
    assert 'fit_overview.svg' in summary
    assert (out_dir / 'camilladsp_full.yaml').exists()
    assert (out_dir / 'camilladsp_filters_only.yaml').exists()
    assert (out_dir / 'fit_overview.svg').exists()
    assert (out_dir / 'fit_left.svg').exists()
    assert (out_dir / 'fit_right.svg').exists()
    assert 'generated_by' in (out_dir / 'fit_report.json').read_text()
    assert 'generated_by' in (out_dir / 'camilladsp_full.yaml').read_text()
    guide = (out_dir / 'README.txt').read_text()
    assert 'headmatch fit results' in guide
    assert 'camilladsp_full.yaml' in guide



def test_iterative_measurement_writes_per_iteration_readme(monkeypatch, tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)

    def fake_run_pipewire_measurement(_spec, paths, _device):
        paths.sweep_wav.write_bytes(b'fake sweep')
        paths.recording_wav.write_bytes(recording.read_bytes())
        return paths.recording_wav

    monkeypatch.setattr('headmatch.pipeline.run_pipewire_measurement', fake_run_pipewire_measurement)

    summaries = iterative_measure_and_fit(
        output_dir=tmp_path / 'iterative',
        sweep_spec=spec,
        target_path=None,
        output_target=None,
        input_target=None,
        iterations=1,
        max_filters=4,
    )

    assert len(summaries) == 1
    guide = (tmp_path / 'iterative' / 'iter_01' / 'README.txt').read_text()
    assert 'headmatch iteration results' in guide
    assert 'iterations_summary.json' in guide
    assert (tmp_path / 'iterative' / 'iter_01' / 'fit_overview.svg').exists()



def test_analyze_accepts_mono_recording_by_duplicating_channel(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    original, _sr = sf.read(str(recording), always_2d=True)
    mono_path = tmp_path / 'mono.wav'
    write_wav(mono_path, original[:, :1], spec.sample_rate)
    result = analyze_measurement(mono_path, spec, out_dir=tmp_path)
    assert np.allclose(result.left_db, result.right_db)



def test_analyze_accepts_multichannel_recording_using_first_two_channels(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    stereo, _sr = sf.read(str(recording), always_2d=True)
    extra = np.column_stack([np.zeros(len(stereo)), np.ones(len(stereo)) * 0.5])
    quad_path = tmp_path / 'quad.wav'
    write_wav(quad_path, np.hstack([stereo, extra]), spec.sample_rate)
    result = analyze_measurement(quad_path, spec, out_dir=tmp_path)
    assert len(result.freqs_hz) > 100
    assert np.max(np.abs(result.left_db - result.right_db)) > 0.1



def test_alignment_handles_long_delay_noise_and_channel_imbalance(tmp_path: Path):
    recording, spec = simulate_headphone_recording(
        tmp_path,
        left_delay=900,
        right_delay=1200,
        noise_scale=0.001,
        right_gain=0.55,
        extra_lead_in_s=0.7,
    )
    result = analyze_measurement(recording, spec, out_dir=tmp_path)
    assert len(result.freqs_hz) > 100
    assert np.isfinite(result.left_db).all()
    assert np.isfinite(result.right_db).all()
    assert np.max(np.abs(result.left_db - result.right_db)) > 0.25
