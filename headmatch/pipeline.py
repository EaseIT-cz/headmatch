"""Measurement-to-fit orchestration pipeline.

Coordinates measurement → analysis → fitting → artifact writing.
Confidence scoring lives in pipeline_confidence.py.
Artifact writing lives in pipeline_artifacts.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .analysis import MeasurementResult, analyze_measurement
from .app_identity import get_app_identity
from .io_utils import save_fr_csv, save_json
from .measure import MeasurementPaths, PipeWireDeviceConfig, run_pipewire_measurement
from .eq_clipping import assess_eq_clipping
from .peq import FilterBudget, PEQBand, fit_peq, peq_chain_response_db
from .pipeline_artifacts import write_fit_artifacts
from .pipeline_confidence import summarize_trustworthiness
from .signals import SweepSpec
from .targets import TargetCurve, create_flat_target, load_curve, resample_curve, clone_target_from_source_target


# Re-export for backward compatibility (tests and callers that import from pipeline)
from .pipeline_artifacts import write_results_guide, RESULTS_GUIDE_NAME  # noqa: F401
from .pipeline_confidence import (  # noqa: F401
    _confidence_penalty,
    ALIGNMENT_SCORE_WARN, ALIGNMENT_SCORE_SEVERE,
    ALIGNMENT_PEAK_WARN, ALIGNMENT_PEAK_SEVERE,
    CHANNEL_MISMATCH_WARN_DB, CHANNEL_MISMATCH_SEVERE_DB,
    ROUGHNESS_WARN_DB, ROUGHNESS_SEVERE_DB,
    RESIDUAL_RMS_WARN_DB, RESIDUAL_RMS_SEVERE_DB,
    RESIDUAL_PEAK_WARN_DB, RESIDUAL_PEAK_SEVERE_DB,
    ALIGNMENT_WEIGHT, ALIGNMENT_PEAK_WEIGHT,
    CHANNEL_MISMATCH_WEIGHT, ROUGHNESS_WEIGHT,
    RESIDUAL_RMS_WEIGHT, RESIDUAL_PEAK_WEIGHT,
    ALIGNMENT_SCORE_WARNING_THRESHOLD, ALIGNMENT_PEAK_WARNING_THRESHOLD,
    SCORE_HIGH_THRESHOLD, SCORE_MEDIUM_THRESHOLD,
)


@dataclass
class IterationSummary:
    iteration: int
    left_rms_error_db: float
    right_rms_error_db: float
    left_max_error_db: float
    right_max_error_db: float


@dataclass
class ResolvedTargetCurves:
    base: TargetCurve
    freqs_hz: np.ndarray
    left_values_db: np.ndarray
    right_values_db: np.ndarray

    @property
    def name(self) -> str:
        return self.base.name

    @property
    def semantics(self) -> str:
        return self.base.semantics


def _resolve_target_curves(result: MeasurementResult, target: TargetCurve) -> ResolvedTargetCurves:
    target_resampled = resample_curve(target, result.freqs_hz)
    if target_resampled.semantics == 'relative':
        left_values = result.left_db + target_resampled.values_db
        right_values = result.right_db + target_resampled.values_db
    else:
        left_values = target_resampled.values_db
        right_values = target_resampled.values_db
    return ResolvedTargetCurves(
        base=target_resampled,
        freqs_hz=result.freqs_hz,
        left_values_db=left_values,
        right_values_db=right_values,
    )


# Keep _summarize_trustworthiness as a thin wrapper for backward compat
def _summarize_trustworthiness(result: MeasurementResult, report: dict):
    return summarize_trustworthiness(result, report)


# Keep _write_fit_artifacts as a thin wrapper for backward compat
def _write_fit_artifacts(out_dir, *, kind, result, target, left_bands, right_bands,
                         report, sample_rate, write_target_curve_csv, filter_budget):
    return write_fit_artifacts(
        out_dir, kind=kind, result=result, target=target,
        left_bands=left_bands, right_bands=right_bands,
        report=report, sample_rate=sample_rate,
        write_target_curve_csv=write_target_curve_csv,
        filter_budget=filter_budget,
    )


def _metrics(freqs_hz: np.ndarray, measured_db: np.ndarray, target_db: np.ndarray) -> tuple[float, float]:
    err = measured_db - target_db
    # Restrict error metrics to the audible band (80-12000 Hz),
    # consistent with the band mask used for roughness/mismatch diagnostics.
    mask = (freqs_hz >= 80) & (freqs_hz <= 12000)
    if not np.any(mask):
        mask = np.ones(len(err), dtype=bool)
    rms = float(np.sqrt(np.mean(err[mask] ** 2)))
    max_abs = float(np.max(np.abs(err[mask])))
    return rms, max_abs


def fit_from_measurement(result: MeasurementResult, target: TargetCurve, sample_rate: int, max_filters: int = 8, *, filter_budget: FilterBudget | None = None) -> tuple[list[PEQBand], list[PEQBand], dict]:
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    resolved_target = _resolve_target_curves(result, target)
    left_eq_target = resolved_target.left_values_db - result.left_db
    right_eq_target = resolved_target.right_values_db - result.right_db
    left_bands = fit_peq(result.freqs_hz, left_eq_target, sample_rate, max_filters=max_filters, budget=filter_budget)
    right_bands = fit_peq(result.freqs_hz, right_eq_target, sample_rate, max_filters=max_filters, budget=filter_budget)
    left_pred = result.left_db + peq_chain_response_db(result.freqs_hz, sample_rate, left_bands)
    right_pred = result.right_db + peq_chain_response_db(result.freqs_hz, sample_rate, right_bands)
    l_rms, l_max = _metrics(result.freqs_hz, left_pred, resolved_target.left_values_db)
    r_rms, r_max = _metrics(result.freqs_hz, right_pred, resolved_target.right_values_db)
    identity = get_app_identity()
    report = {
        'generated_by': identity.as_metadata(),
        'predicted_left_rms_error_db': l_rms,
        'predicted_right_rms_error_db': r_rms,
        'predicted_left_max_error_db': l_max,
        'predicted_right_max_error_db': r_max,
        'measurement_diagnostics': result.diagnostics,
        'filter_budget': {
            'family': filter_budget.family,
            'max_filters': filter_budget.max_filters,
            'fill_policy': filter_budget.fill_policy,
            'profile': filter_budget.profile,
        },
        'left_bands': [asdict(b) for b in left_bands],
        'right_bands': [asdict(b) for b in right_bands],
    }
    # Assess EQ clipping potential
    clipping_assessment = assess_eq_clipping(result.freqs_hz, sample_rate, left_bands, right_bands)
    report['eq_clipping'] = {
        'will_clip': clipping_assessment.will_clip,
        'left_peak_boost_db': clipping_assessment.left_peak_boost_db,
        'right_peak_boost_db': clipping_assessment.right_peak_boost_db,
        'preamp_db': clipping_assessment.total_preamp_db,
        'headroom_loss_db': clipping_assessment.headroom_loss_db,
        'quality_concern': clipping_assessment.quality_concern,
    }
    report['confidence'] = summarize_trustworthiness(result, report).to_dict()
    return left_bands, right_bands, report


def process_single_measurement(recording_wav: str | Path, out_dir: str | Path, sweep_spec: SweepSpec, target_path: str | Path | None = None, max_filters: int = 8, *, filter_budget: FilterBudget | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_measurement(recording_wav, sweep_spec, out_dir=out_dir)
    target = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    left_bands, right_bands, report = fit_from_measurement(result, target, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget)
    write_fit_artifacts(
        out_dir,
        kind='fit',
        result=result,
        target=target,
        left_bands=left_bands,
        right_bands=right_bands,
        report=report,
        sample_rate=sweep_spec.sample_rate,
        write_target_curve_csv=True,
        filter_budget=filter_budget,
    )
    return report


def build_clone_curve(source_curve_path: str | Path, target_curve_path: str | Path, out_path: str | Path) -> TargetCurve:
    return clone_target_from_source_target(source_curve_path, target_curve_path, out_path)


def _average_measurements(results: list[MeasurementResult]) -> MeasurementResult:
    """Average multiple measurement results into a single combined result."""
    left_db = np.mean([r.left_db for r in results], axis=0)
    right_db = np.mean([r.right_db for r in results], axis=0)
    left_raw_db = np.mean([r.left_raw_db for r in results], axis=0)
    right_raw_db = np.mean([r.right_raw_db for r in results], axis=0)
    avg_diagnostics: Dict[str, float] = {}
    all_keys = results[0].diagnostics.keys()
    for key in all_keys:
        values = [r.diagnostics.get(key, 0.0) for r in results]
        avg_diagnostics[key] = float(np.mean(values))
    return MeasurementResult(
        freqs_hz=results[0].freqs_hz,
        left_db=left_db,
        right_db=right_db,
        left_raw_db=left_raw_db,
        right_raw_db=right_raw_db,
        diagnostics=avg_diagnostics,
    )


IterationMode = str  # 'independent' or 'average'


def iterative_measure_and_fit(
    output_dir: str | Path,
    sweep_spec: SweepSpec,
    target_path: str | Path | None,
    output_target: str | None,
    input_target: str | None,
    iterations: int = 2,
    max_filters: int = 8,
    *,
    filter_budget: FilterBudget | None = None,
    iteration_mode: str = 'independent',
) -> list[dict]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    target_curve: Optional[TargetCurve] = None
    summaries = []
    all_results: list[MeasurementResult] = []

    for i in range(1, iterations + 1):
        iter_dir = output_dir / f'iter_{i:02d}'
        iter_dir.mkdir(exist_ok=True)
        recording = iter_dir / 'recording.wav'
        sweep = iter_dir / 'sweep.wav'
        run_pipewire_measurement(sweep_spec, MeasurementPaths(sweep, recording), PipeWireDeviceConfig(output_target, input_target))
        result = analyze_measurement(recording, sweep_spec, iter_dir)
        all_results.append(result)
        if target_curve is None:
            target_curve = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)

    if iteration_mode == 'average' and len(all_results) > 1:
        averaged = _average_measurements(all_results)
        save_fr_csv(output_dir / 'measurement_left.csv', averaged.freqs_hz, averaged.left_db)
        save_fr_csv(output_dir / 'measurement_right.csv', averaged.freqs_hz, averaged.right_db)
        left_bands, right_bands, report = fit_from_measurement(averaged, target_curve, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget)  # type: ignore[arg-type]
        run_summary = write_fit_artifacts(
            output_dir,
            kind='fit',
            result=averaged,
            target=target_curve,  # type: ignore[arg-type]
            left_bands=left_bands,
            right_bands=right_bands,
            report=report,
            sample_rate=sweep_spec.sample_rate,
            write_target_curve_csv=True,
            filter_budget=filter_budget,
        )
        predicted = run_summary['predicted_error_db']
        summaries.append(asdict(IterationSummary(0, predicted['left_rms'], predicted['right_rms'], predicted['left_max'], predicted['right_max'])))
    else:
        for i, result in enumerate(all_results, 1):
            iter_dir = output_dir / f'iter_{i:02d}'
            left_bands, right_bands, report = fit_from_measurement(result, target_curve, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget)  # type: ignore[arg-type]
            run_summary = write_fit_artifacts(
                iter_dir,
                kind='iteration',
                result=result,
                target=target_curve,  # type: ignore[arg-type]
                left_bands=left_bands,
                right_bands=right_bands,
                report=report,
                sample_rate=sweep_spec.sample_rate,
                write_target_curve_csv=False,
                filter_budget=filter_budget,
            )
            predicted = run_summary['predicted_error_db']
            summaries.append(asdict(IterationSummary(i, predicted['left_rms'], predicted['right_rms'], predicted['left_max'], predicted['right_max'])))

    identity = get_app_identity()
    save_json(output_dir / 'iterations_summary.json', {'generated_by': identity.as_metadata(), 'iterations': summaries, 'count': len(summaries), 'mode': iteration_mode})
    return summaries
