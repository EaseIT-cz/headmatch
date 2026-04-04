from __future__ import annotations
import pytest

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from headmatch.analysis import MeasurementResult, analyze_measurement
from headmatch.io_utils import write_wav
from headmatch.peq import FilterBudget, peq_chain_response_db
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





def test_fit_from_measurement_reports_explicit_filter_budget_for_default_and_exact_modes(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    result = analyze_measurement(recording, spec, out_dir=tmp_path)
    target = TargetCurve(result.freqs_hz, np.zeros_like(result.freqs_hz), 'flat')

    _left_default, _right_default, default_report = fit_from_measurement(result, target, spec.sample_rate, max_filters=3)
    left_exact, right_exact, exact_report = fit_from_measurement(
        result,
        target,
        spec.sample_rate,
        filter_budget=FilterBudget(max_filters=3, fill_policy='exact_n'),
    )

    assert default_report['filter_budget'] == {'family': 'peq', 'max_filters': 3, 'fill_policy': 'up_to_n', 'profile': None}
    assert exact_report['filter_budget'] == {'family': 'peq', 'max_filters': 3, 'fill_policy': 'exact_n', 'profile': None}
    assert len(left_exact) == 3
    assert len(right_exact) == 3


def test_process_single_measurement_writes_filter_budget_into_run_summary(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    out_dir = tmp_path / 'fit_exact'
    report = process_single_measurement(
        recording,
        out_dir,
        spec,
        target_path=None,
        filter_budget=FilterBudget(max_filters=3, fill_policy='exact_n'),
    )

    assert report['filter_budget']['fill_policy'] == 'exact_n'
    summary = (out_dir / 'run_summary.json').read_text()
    assert '"filter_budget"' in summary
    assert '"fill_policy": "exact_n"' in summary


def test_process_single_measurement_writes_direct_fixed_graphiceq_artifact(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    out_dir = tmp_path / 'fit_graphiceq'
    report = process_single_measurement(
        recording,
        out_dir,
        spec,
        target_path=None,
        filter_budget=FilterBudget(family='graphic_eq', max_filters=10, profile='geq_10_band'),
    )

    assert report['filter_budget'] == {
        'family': 'graphic_eq',
        'max_filters': 10,
        'fill_policy': 'exact_n',
        'profile': 'geq_10_band',
    }
    fixed_text = (out_dir / 'equalizer_apo_fixed_graphiceq.txt').read_text()
    dense_text = (out_dir / 'equalizer_apo_graphiceq.txt').read_text()
    summary = (out_dir / 'run_summary.json').read_text()
    guide = (out_dir / 'README.txt').read_text()
    assert '; Generated directly from the fixed-band GraphicEQ fitting backend.' in fixed_text
    assert 'GraphicEQ:' in fixed_text
    assert 'GraphicEQ:' in dense_text
    assert 'equalizer_apo_fixed_graphiceq.txt' in guide
    assert '"family": "graphic_eq"' in summary
    assert '"profile": "geq_10_band"' in summary


def test_process_single_measurement_writes_run_summary(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    out_dir = tmp_path / 'fit'
    report = process_single_measurement(recording, out_dir, spec, target_path=None, max_filters=4)
    assert report['predicted_left_rms_error_db'] >= 0
    summary = (out_dir / 'run_summary.json').read_text()
    assert 'predicted_error_db' in summary
    assert 'confidence' in summary
    assert 'generated_by' in summary
    assert 'fit_overview.svg' in summary
    assert (out_dir / 'camilladsp_full.yaml').exists()
    assert (out_dir / 'camilladsp_filters_only.yaml').exists()
    assert (out_dir / 'equalizer_apo.txt').exists()
    assert (out_dir / 'equalizer_apo_graphiceq.txt').exists()
    assert (out_dir / 'fit_overview.svg').exists()
    assert (out_dir / 'fit_left.svg').exists()
    assert (out_dir / 'fit_right.svg').exists()
    assert 'generated_by' in (out_dir / 'fit_report.json').read_text()
    assert 'generated_by' in (out_dir / 'camilladsp_full.yaml').read_text()
    guide = (out_dir / 'README.txt').read_text()
    assert 'headmatch fit results' in guide
    assert 'camilladsp_full.yaml' in guide
    assert 'equalizer_apo.txt' in guide
    assert 'equalizer_apo_graphiceq.txt' in guide
    assert 'GraphicEQ:' in (out_dir / 'equalizer_apo_graphiceq.txt').read_text()
    assert 'What to try next' not in guide





def test_confidence_summary_marks_clean_run_as_trustworthy(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    out_dir = tmp_path / 'fit_clean'
    report = process_single_measurement(recording, out_dir, spec, target_path=None, max_filters=4)
    confidence = report['confidence']
    assert confidence['score'] >= 70
    assert confidence['label'] in {'high', 'medium'}
    assert 'alignment_reference_score' in confidence['metrics']


def test_confidence_summary_flags_suspicious_run(tmp_path: Path):
    recording, spec = simulate_headphone_recording(
        tmp_path,
        noise_scale=0.08,
        right_gain=0.15,
        extra_lead_in_s=4.0,
        left_delay=4500,
        right_delay=7000,
    )
    out_dir = tmp_path / 'fit_suspicious'
    report = process_single_measurement(recording, out_dir, spec, target_path=None, max_filters=4)
    confidence = report['confidence']
    assert confidence['label'] == 'low'
    assert confidence['score'] < 65
    assert confidence['warnings']
    summary = (out_dir / 'run_summary.json').read_text()
    guide = (out_dir / 'README.txt').read_text()
    assert 'This run looks suspicious.' in summary
    assert 'Confidence: low' in guide
    assert 'What to try next:' in guide
    assert 'Try one fresh rerun before keeping this EQ preset.' in guide


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
    assert (tmp_path / 'iterative' / 'iter_01' / 'equalizer_apo.txt').exists()
    assert (tmp_path / 'iterative' / 'iter_01' / 'equalizer_apo_graphiceq.txt').exists()



def test_analyze_rejects_mono_recording(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    original, _sr = sf.read(str(recording), always_2d=True)
    mono_path = tmp_path / 'mono.wav'
    write_wav(mono_path, original[:, :1], spec.sample_rate)
    with pytest.raises(ValueError, match="mono capture"):
        analyze_measurement(mono_path, spec, out_dir=tmp_path)



def test_analyze_accepts_multichannel_recording_using_first_two_channels(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    stereo, _sr = sf.read(str(recording), always_2d=True)
    extra = np.column_stack([np.zeros(len(stereo)), np.ones(len(stereo)) * 0.5])
    quad_path = tmp_path / 'quad.wav'
    write_wav(quad_path, np.hstack([stereo, extra]), spec.sample_rate)
    result = analyze_measurement(quad_path, spec, out_dir=tmp_path)
    assert len(result.freqs_hz) > 100
    assert np.max(np.abs(result.left_db - result.right_db)) > 0.1

def test_analyze_rejects_duplicated_channel_capture(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    stereo, _sr = sf.read(str(recording), always_2d=True)
    dup_path = tmp_path / 'duplicated.wav'
    write_wav(dup_path, np.column_stack([stereo[:, 0], stereo[:, 0]]), spec.sample_rate)
    with pytest.raises(ValueError, match="duplicated-channel"):
        analyze_measurement(dup_path, spec, out_dir=tmp_path)


def test_analyze_rejects_duplicated_channel_in_multichannel_capture(tmp_path: Path):
    recording, spec = simulate_headphone_recording(tmp_path)
    stereo, _sr = sf.read(str(recording), always_2d=True)
    quad_path = tmp_path / 'quad_dup.wav'
    ch0 = stereo[:, 0]
    write_wav(quad_path, np.column_stack([ch0, ch0, stereo[:, 1], stereo[:, 1]]), spec.sample_rate)
    with pytest.raises(ValueError, match="duplicated-channel"):
        analyze_measurement(quad_path, spec, out_dir=tmp_path)




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


def test_relative_target_zero_delta_is_treated_as_noop_clone_match():
    freqs = np.array([20.0, 1000.0, 20000.0])
    result = MeasurementResult(
        freqs_hz=freqs,
        left_db=np.array([1.0, 0.0, -1.0]),
        right_db=np.array([2.0, 0.0, -2.0]),
        left_raw_db=np.array([1.0, 0.0, -1.0]),
        right_raw_db=np.array([2.0, 0.0, -2.0]),
        diagnostics={
            'alignment_reference_score': 0.99,
            'alignment_peak_ratio': 0.99,
            'channel_mismatch_rms_db': 0.1,
            'left_roughness_db': 0.1,
            'right_roughness_db': 0.1,
            'capture_rms_dbfs': -20.0,
        },
    )
    target = TargetCurve(freqs, np.zeros_like(freqs), 'clone_delta', semantics='relative')

    left_bands, right_bands, report = fit_from_measurement(result, target, 48000, max_filters=1)

    assert left_bands == []
    assert right_bands == []
    assert report['predicted_left_rms_error_db'] == 0.0
    assert report['predicted_right_rms_error_db'] == 0.0



def test_process_single_measurement_relative_target_exports_effective_per_channel_targets(monkeypatch, tmp_path: Path):
    freqs = np.array([20.0, 1000.0, 20000.0])
    result = MeasurementResult(
        freqs_hz=freqs,
        left_db=np.array([1.0, 0.0, -1.0]),
        right_db=np.array([2.0, 0.0, -2.0]),
        left_raw_db=np.array([1.0, 0.0, -1.0]),
        right_raw_db=np.array([2.0, 0.0, -2.0]),
        diagnostics={
            'alignment_reference_score': 0.99,
            'alignment_peak_ratio': 0.99,
            'channel_mismatch_rms_db': 0.1,
            'left_roughness_db': 0.1,
            'right_roughness_db': 0.1,
            'capture_rms_dbfs': -20.0,
        },
    )
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, pre_silence_s=0.0, post_silence_s=0.0, amplitude=0.1)
    target_csv = tmp_path / 'clone_target.csv'
    target_csv.write_text(
        '# headmatch_target_semantics=relative\n'
        'frequency_hz,target_db\n'
        '20,2\n'
        '1000,0\n'
        '20000,-2\n'
    )

    monkeypatch.setattr('headmatch.pipeline.analyze_measurement', lambda *_args, **_kwargs: result)

    out_dir = tmp_path / 'fit_relative_export'
    process_single_measurement('ignored.wav', out_dir, spec, target_path=target_csv, max_filters=0)

    rows = (out_dir / 'target_curve.csv').read_text().splitlines()
    graphiceq = (out_dir / 'equalizer_apo_graphiceq.txt').read_text()

    assert rows == [
        'frequency_hz,left_target_db,right_target_db',
        '20.0,3.0,4.0',
        '1000.0,0.0,0.0',
        '20000.0,-3.0,-4.0',
    ]
    assert 'GraphicEQ: 20.00 2.00; 1000.00 0.00; 20000.00 -2.00' in graphiceq
    assert 'GraphicEQ: 20.00 2.00; 1000.00 0.00; 20000.00 -2.00' in graphiceq
