from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import signal

from headmatch import cli
from headmatch.contracts import FrontendConfig
from headmatch.io_utils import load_fr_csv, write_wav
from headmatch.peq import PEQBand, peq_chain_response_db
from headmatch.signals import SweepSpec, generate_log_sweep


def _synthetic_sweep_spec() -> SweepSpec:
    return SweepSpec(
        sample_rate=48000,
        duration_s=1.25,
        pre_silence_s=0.05,
        post_silence_s=0.1,
        amplitude=0.35,
    )


def _peaking_sos(sample_rate: int, fc: float, q: float, gain_db: float) -> np.ndarray:
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / sample_rate
    alpha = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    b = np.array([1 + alpha * A, -2 * c, 1 - alpha * A])
    a = np.array([1 + alpha / A, -2 * c, 1 - alpha / A])
    return signal.tf2sos(b, a)


def build_synthetic_recording(tmp_path: Path) -> tuple[Path, SweepSpec]:
    spec = _synthetic_sweep_spec()
    stereo, _ = generate_log_sweep(spec)

    left_sos = np.vstack(
        [
            _peaking_sos(spec.sample_rate, 85, 0.8, 5.0),
            _peaking_sos(spec.sample_rate, 2800, 1.4, 4.5),
            _peaking_sos(spec.sample_rate, 7600, 2.8, -3.0),
        ]
    )
    right_sos = np.vstack(
        [
            _peaking_sos(spec.sample_rate, 95, 0.75, 4.0),
            _peaking_sos(spec.sample_rate, 3400, 1.6, 5.0),
            _peaking_sos(spec.sample_rate, 9000, 3.0, -2.5),
        ]
    )

    left = signal.sosfilt(left_sos, stereo[:, 0])
    right = signal.sosfilt(right_sos, stereo[:, 1]) * 0.96

    left = np.concatenate([np.zeros(90), left[:-90]]) + 0.00015 * np.random.default_rng(0).standard_normal(len(left))
    right = np.concatenate([np.zeros(120), right[:-120]]) + 0.00015 * np.random.default_rng(1).standard_normal(len(right))

    recording = np.column_stack([left, right])
    recording_path = tmp_path / "recording.wav"
    write_wav(recording_path, recording, spec.sample_rate)
    return recording_path, spec


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def flat_target_csv() -> Path:
    return Path(__file__).with_name('fixtures') / 'flat_target.csv'


def _rms_error(values_db: np.ndarray, target_db: np.ndarray) -> float:
    return float(np.sqrt(np.mean((values_db - target_db) ** 2)))


def _predicted_errors(out_dir: Path, sample_rate: int) -> dict[str, float]:
    freqs, left = load_fr_csv(out_dir / "measurement_left.csv")
    _, right = load_fr_csv(out_dir / "measurement_right.csv")
    target_path = out_dir / "target_curve.csv"
    if target_path.exists():
        with target_path.open() as handle:
            rows = [line.strip().split(',') for line in handle if line.strip()]
        header = rows[0]
        values = np.array([[float(cell) for cell in row[1:]] for row in rows[1:]], dtype=np.float64)
        if header[1:] == ['left_target_db', 'right_target_db']:
            left_target = values[:, 0]
            right_target = values[:, 1]
        else:
            left_target = values[:, 0]
            right_target = values[:, 0]
    else:
        left_target = np.zeros_like(freqs)
        right_target = np.zeros_like(freqs)
    report = _read_json(out_dir / "fit_report.json")

    left_bands = [PEQBand(**band) for band in report["left_bands"]]
    right_bands = [PEQBand(**band) for band in report["right_bands"]]

    left_before = _rms_error(left, left_target)
    right_before = _rms_error(right, right_target)
    left_after = _rms_error(left + peq_chain_response_db(freqs, sample_rate, left_bands), left_target)
    right_after = _rms_error(right + peq_chain_response_db(freqs, sample_rate, right_bands), right_target)

    return {
        "left_before": left_before,
        "right_before": right_before,
        "left_after": left_after,
        "right_after": right_after,
    }


def _patch_cli_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), tmp_path / "config.json", False),
    )
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)


def test_fit_cli_end_to_end_on_synthetic_recording(monkeypatch, tmp_path: Path):
    recording, spec = build_synthetic_recording(tmp_path)
    out_dir = tmp_path / "fit"
    _patch_cli_config(monkeypatch, tmp_path)

    target_csv = flat_target_csv()

    cli.main(
        [
            "fit",
            "--recording",
            str(recording),
            "--out-dir",
            str(out_dir),
            "--target-csv",
            str(target_csv),
            "--sample-rate",
            str(spec.sample_rate),
            "--duration",
            str(spec.duration_s),
            "--pre-silence",
            str(spec.pre_silence_s),
            "--post-silence",
            str(spec.post_silence_s),
            "--amplitude",
            str(spec.amplitude),
            "--max-filters",
            "5",
        ]
    )

    summary = _read_json(out_dir / "run_summary.json")
    report = _read_json(out_dir / "fit_report.json")
    guide = (out_dir / "README.txt").read_text()
    errors = _predicted_errors(out_dir, spec.sample_rate)

    assert errors["left_after"] < errors["left_before"] * 0.5
    assert errors["right_after"] < errors["right_before"] * 0.5
    assert summary["kind"] == "fit"
    assert summary["target"] == "flat_target"
    assert summary["filters"]["left"] >= 2
    assert summary["filters"]["right"] >= 2
    assert summary["predicted_error_db"]["left_rms"] == report["predicted_left_rms_error_db"]
    assert summary["predicted_error_db"]["right_rms"] == report["predicted_right_rms_error_db"]
    assert abs(summary["predicted_error_db"]["left_rms"] - errors["left_after"]) < 1e-6
    assert abs(summary["predicted_error_db"]["right_rms"] - errors["right_after"]) < 1e-6
    assert (out_dir / "camilladsp_full.yaml").exists()
    assert (out_dir / "camilladsp_filters_only.yaml").exists()
    assert (out_dir / "equalizer_apo.txt").exists()
    assert (out_dir / "equalizer_apo_graphiceq.txt").exists()
    assert (out_dir / "measurement_left.csv").exists()
    assert (out_dir / "measurement_right.csv").exists()
    assert (out_dir / "target_curve.csv").exists()
    assert (out_dir / "fit_overview.svg").exists()
    assert (out_dir / "fit_left.svg").exists()
    assert (out_dir / "fit_right.svg").exists()
    assert summary["plots"]["overview"].endswith("fit_overview.svg")
    assert "headmatch fit results" in guide
    assert "camilladsp_full.yaml" in guide
    assert "equalizer_apo.txt" in guide
    assert "equalizer_apo_graphiceq.txt" in guide



def test_fit_cli_supports_fixed_band_graphiceq_backend(monkeypatch, tmp_path: Path):
    recording, spec = build_synthetic_recording(tmp_path)
    out_dir = tmp_path / 'fit_graphiceq'
    _patch_cli_config(monkeypatch, tmp_path)

    cli.main(
        [
            'fit',
            '--recording', str(recording),
            '--out-dir', str(out_dir),
            '--target-csv', str(flat_target_csv()),
            '--sample-rate', str(spec.sample_rate),
            '--duration', str(spec.duration_s),
            '--pre-silence', str(spec.pre_silence_s),
            '--post-silence', str(spec.post_silence_s),
            '--amplitude', str(spec.amplitude),
            '--filter-family', 'graphic_eq',
            '--graphic-eq-profile', 'geq_10_band',
            '--max-filters', '10',
        ]
    )

    summary = _read_json(out_dir / 'run_summary.json')
    report = _read_json(out_dir / 'fit_report.json')
    fixed_text = (out_dir / 'equalizer_apo_fixed_graphiceq.txt').read_text()
    assert summary['filter_budget'] == {
        'family': 'graphic_eq',
        'max_filters': 10,
        'fill_policy': 'exact_n',
        'profile': 'geq_10_band',
    }
    assert len(report['left_bands']) == 10
    assert len(report['right_bands']) == 10
    assert '; Generated directly from the fixed-band GraphicEQ fitting backend.' in fixed_text
    assert (out_dir / 'equalizer_apo_graphiceq.txt').exists()


def test_start_cli_online_workflow_uses_shared_pipeline_and_writes_iteration_outputs(monkeypatch, tmp_path: Path):
    recording, spec = build_synthetic_recording(tmp_path)
    out_dir = tmp_path / "start"
    _patch_cli_config(monkeypatch, tmp_path)

    def fake_run_pipewire_measurement(_spec, paths, _device):
        paths.sweep_wav.write_bytes(b"synthetic sweep")
        paths.recording_wav.write_bytes(recording.read_bytes())
        return paths.recording_wav

    monkeypatch.setattr("headmatch.pipeline.run_pipewire_measurement", fake_run_pipewire_measurement)

    target_csv = flat_target_csv()

    cli.main(
        [
            "start",
            "--out-dir",
            str(out_dir),
            "--target-csv",
            str(target_csv),
            "--sample-rate",
            str(spec.sample_rate),
            "--duration",
            str(spec.duration_s),
            "--pre-silence",
            str(spec.pre_silence_s),
            "--post-silence",
            str(spec.post_silence_s),
            "--amplitude",
            str(spec.amplitude),
            "--iterations",
            "1",
            "--max-filters",
            "5",
        ]
    )

    iter_dir = out_dir / "iter_01"
    summary = _read_json(iter_dir / "run_summary.json")
    iterations_summary = _read_json(out_dir / "iterations_summary.json")
    errors = _predicted_errors(iter_dir, spec.sample_rate)

    assert iterations_summary["count"] == 1
    assert len(iterations_summary["iterations"]) == 1
    assert summary["kind"] == "iteration"
    assert errors["left_after"] < errors["left_before"] * 0.5
    assert errors["right_after"] < errors["right_before"] * 0.5
    assert abs(iterations_summary["iterations"][0]["left_rms_error_db"] - errors["left_after"]) < 1e-6
    assert abs(iterations_summary["iterations"][0]["right_rms_error_db"] - errors["right_after"]) < 1e-6
    assert (iter_dir / "fit_report.json").exists()
    assert (iter_dir / "camilladsp_full.yaml").exists()
    assert (iter_dir / "camilladsp_filters_only.yaml").exists()
    assert (iter_dir / "equalizer_apo.txt").exists()
    assert (iter_dir / "equalizer_apo_graphiceq.txt").exists()
    assert (iter_dir / "recording.wav").exists()
    assert (iter_dir / "sweep.wav").exists()
    assert (iter_dir / "fit_overview.svg").exists()
    guide = (iter_dir / "README.txt").read_text()
    assert "headmatch iteration results" in guide
    assert "equalizer_apo.txt" in guide


def test_fit_cli_relative_clone_target_uses_effective_channel_targets(monkeypatch, tmp_path: Path):
    recording, spec = build_synthetic_recording(tmp_path)
    out_dir = tmp_path / 'fit_relative'
    _patch_cli_config(monkeypatch, tmp_path)

    clone_target = tmp_path / 'clone_target.csv'
    clone_target.write_text(
        '# headmatch_target_semantics=relative\n'
        'frequency_hz,target_db\n'
        '20,2.5\n'
        '1000,0\n'
        '20000,-2.5\n'
    )

    cli.main([
        'fit', '--recording', str(recording), '--out-dir', str(out_dir), '--target-csv', str(clone_target),
        '--sample-rate', str(spec.sample_rate), '--duration', str(spec.duration_s), '--pre-silence', str(spec.pre_silence_s),
        '--post-silence', str(spec.post_silence_s), '--amplitude', str(spec.amplitude), '--max-filters', '5',
    ])

    errors = _predicted_errors(out_dir, spec.sample_rate)
    summary = _read_json(out_dir / 'run_summary.json')
    target_curve_text = (out_dir / 'target_curve.csv').read_text().splitlines()[0]

    assert errors['left_after'] < 0.8
    assert errors['right_after'] < 0.8
    assert summary['target'] == 'clone_target'
    assert target_curve_text == 'frequency_hz,left_target_db,right_target_db'
