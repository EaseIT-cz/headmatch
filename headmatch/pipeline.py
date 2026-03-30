from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .analysis import MeasurementResult, analyze_measurement
from .exporters import export_camilladsp_filter_snippet_yaml, export_camilladsp_filters_yaml
from .io_utils import save_fr_csv, save_json
from .measure import MeasurementPaths, PipeWireDeviceConfig, run_pipewire_measurement
from .peq import PEQBand, fit_peq, peq_chain_response_db
from .signals import SweepSpec
from .targets import TargetCurve, create_flat_target, load_curve, resample_curve, clone_target_from_source_target


@dataclass
class IterationSummary:
    iteration: int
    left_rms_error_db: float
    right_rms_error_db: float
    left_max_error_db: float
    right_max_error_db: float



def _metrics(measured_db: np.ndarray, target_db: np.ndarray) -> tuple[float, float]:
    err = measured_db - target_db
    mask = (np.arange(len(err)) >= 0)
    rms = float(np.sqrt(np.mean(err[mask] ** 2)))
    max_abs = float(np.max(np.abs(err[mask])))
    return rms, max_abs



def fit_from_measurement(result: MeasurementResult, target: TargetCurve, sample_rate: int, max_filters: int = 8) -> tuple[list[PEQBand], list[PEQBand], dict]:
    target_resampled = resample_curve(target, result.freqs_hz)
    left_eq_target = target_resampled.values_db - result.left_db
    right_eq_target = target_resampled.values_db - result.right_db
    left_bands = fit_peq(result.freqs_hz, left_eq_target, sample_rate, max_filters=max_filters)
    right_bands = fit_peq(result.freqs_hz, right_eq_target, sample_rate, max_filters=max_filters)
    left_pred = result.left_db + peq_chain_response_db(result.freqs_hz, sample_rate, left_bands)
    right_pred = result.right_db + peq_chain_response_db(result.freqs_hz, sample_rate, right_bands)
    l_rms, l_max = _metrics(left_pred, target_resampled.values_db)
    r_rms, r_max = _metrics(right_pred, target_resampled.values_db)
    report = {
        'predicted_left_rms_error_db': l_rms,
        'predicted_right_rms_error_db': r_rms,
        'predicted_left_max_error_db': l_max,
        'predicted_right_max_error_db': r_max,
        'left_bands': [asdict(b) for b in left_bands],
        'right_bands': [asdict(b) for b in right_bands],
    }
    return left_bands, right_bands, report



def process_single_measurement(recording_wav: str | Path, out_dir: str | Path, sweep_spec: SweepSpec, target_path: str | Path | None = None, max_filters: int = 8) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_measurement(recording_wav, sweep_spec, out_dir=out_dir)
    target = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
    left_bands, right_bands, report = fit_from_measurement(result, target, sweep_spec.sample_rate, max_filters=max_filters)
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', left_bands, right_bands, samplerate=sweep_spec.sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)
    save_fr_csv(out_dir / 'target_curve.csv', result.freqs_hz, resample_curve(target, result.freqs_hz).values_db, 'target_db')
    save_json(out_dir / 'fit_report.json', report)
    return report



def build_clone_curve(source_curve_path: str | Path, target_curve_path: str | Path, out_path: str | Path) -> TargetCurve:
    return clone_target_from_source_target(source_curve_path, target_curve_path, out_path)



def iterative_measure_and_fit(
    output_dir: str | Path,
    sweep_spec: SweepSpec,
    target_path: str | Path | None,
    output_target: str | None,
    input_target: str | None,
    iterations: int = 2,
    max_filters: int = 8,
) -> list[dict]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_curve: Optional[TargetCurve] = None
    summaries = []
    for i in range(1, iterations + 1):
        iter_dir = output_dir / f'iter_{i:02d}'
        iter_dir.mkdir(exist_ok=True)
        recording = iter_dir / 'recording.wav'
        sweep = iter_dir / 'sweep.wav'
        run_pipewire_measurement(sweep_spec, MeasurementPaths(sweep, recording), PipeWireDeviceConfig(output_target, input_target))
        result = analyze_measurement(recording, sweep_spec, iter_dir)
        if target_curve is None:
            target_curve = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
        left_bands, right_bands, report = fit_from_measurement(result, target_curve, sweep_spec.sample_rate, max_filters=max_filters)
        export_camilladsp_filters_yaml(iter_dir / 'camilladsp_full.yaml', left_bands, right_bands, samplerate=sweep_spec.sample_rate)
        export_camilladsp_filter_snippet_yaml(iter_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)
        predicted_left = result.left_db + peq_chain_response_db(result.freqs_hz, sweep_spec.sample_rate, left_bands)
        predicted_right = result.right_db + peq_chain_response_db(result.freqs_hz, sweep_spec.sample_rate, right_bands)
        t = resample_curve(target_curve, result.freqs_hz).values_db
        l_rms, l_max = _metrics(predicted_left, t)
        r_rms, r_max = _metrics(predicted_right, t)
        summary = IterationSummary(i, l_rms, r_rms, l_max, r_max)
        summaries.append(asdict(summary))
        save_json(iter_dir / 'fit_report.json', report)
    save_json(output_dir / 'iterations_summary.json', {'iterations': summaries})
    return summaries
