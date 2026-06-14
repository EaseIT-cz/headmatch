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


def fit_from_measurement(result: MeasurementResult, target: TargetCurve, sample_rate: int, max_filters: int = 8, *, filter_budget: FilterBudget | None = None, hearing_profile=None) -> tuple[list[PEQBand], list[PEQBand], dict]:
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    resolved_target = _resolve_target_curves(result, target)
    if hearing_profile is not None:
        from .hearing_test import compute_compensation_curve
        compensation = compute_compensation_curve(hearing_profile, result.freqs_hz)
        left_eq_target = (resolved_target.left_values_db + compensation) - result.left_db
        right_eq_target = (resolved_target.right_values_db + compensation) - result.right_db
    else:
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
    report['hearing_compensation_applied'] = hearing_profile is not None
    return left_bands, right_bands, report


def process_single_measurement(recording_wav: str | Path, out_dir: str | Path, sweep_spec: SweepSpec, target_path: str | Path | None = None, max_filters: int = 8, *, filter_budget: FilterBudget | None = None, hearing_profile=None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_measurement(recording_wav, sweep_spec, out_dir=out_dir)
    target = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    left_bands, right_bands, report = fit_from_measurement(result, target, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget, hearing_profile=hearing_profile)
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


def fit_from_hearing_profile(
    profile,
    sample_rate: int,
    target_path: str | Path | None = None,
    max_filters: int = 8,
    *,
    filter_budget: FilterBudget | None = None,
) -> tuple[list[PEQBand], list[PEQBand], dict]:
    """
    Fit PEQ bands from a hearing profile alone — no headphone measurement needed.

    Assumes the headphone has a flat frequency response. The combined EQ target is:
        eq_target(f) = target(f) + hearing_compensation(f)
    where compensation comes from the half-gain rule (Lybarger 1944).
    """
    from .hearing_test import compute_relative_compensation, eq_bands_from_gain_points
    from .signals import geometric_log_grid

    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    # Modest grid used only for the prediction/clipping metrics and target
    # sampling — NOT for manufacturing EQ resolution. The hearing test has only
    # ~7 measured points, so the EQ is built directly from those (see
    # docs/designs/measurement-resolution-eq.md).
    freqs = geometric_log_grid(20.0, 20000.0, 48)

    if target_path:
        target = load_curve(target_path)
    else:
        target = create_flat_target(freqs)
    target_resampled = resample_curve(target, freqs)
    tfreqs = np.asarray(target.freqs_hz, dtype=float)
    tvals = np.asarray(target.values_db, dtype=float)

    # Per-ear, calibration-invariant relative compensation (Part B): reference each
    # ear's thresholds to its own 1 kHz and subtract the normal threshold shape.
    # See docs/designs/calibration-robust-hearing.md.
    left_comp, right_comp = compute_relative_compensation(profile)
    target_grid = np.interp(np.log10(freqs), np.log10(tfreqs), tvals, left=float(tvals[0]), right=float(tvals[-1]))
    target_is_flat = not bool(np.any(np.abs(tvals) > 0.05))

    def _ear_bands_and_target(comp: dict):
        # Sparse hearing compensation as peaking filters at the measured frequencies.
        hearing_bands = eq_bands_from_gain_points(comp, sample_rate=sample_rate, max_filters=filter_budget.max_filters)
        if target_is_flat:
            # Hearing only: keep the honest, sparse measured-resolution bands.
            return hearing_bands, peq_chain_response_db(freqs, sample_rate, hearing_bands)
        # A tonal target is layered on. Render the hearing bumps as a curve, add the
        # (smooth, dense) target, and re-fit the combined curve with fit_peq, which
        # places low/high SHELVES at tilted edges + peaking for mid features — so the
        # Harman bass/treble tilt is smooth instead of rippled.
        combined = target_grid + peq_chain_response_db(freqs, sample_rate, hearing_bands)
        return fit_peq(freqs, combined, sample_rate, budget=filter_budget), combined

    left_bands, left_target = _ear_bands_and_target(left_comp)
    right_bands, right_target = _ear_bands_and_target(right_comp)

    left_pred = peq_chain_response_db(freqs, sample_rate, left_bands)
    right_pred = peq_chain_response_db(freqs, sample_rate, right_bands)
    l_rms, l_max = _metrics(freqs, left_pred, left_target)
    r_rms, r_max = _metrics(freqs, right_pred, right_target)

    identity = get_app_identity()
    report = {
        'generated_by': identity.as_metadata(),
        'mode': 'hearing_only',
        'target': target_resampled.name,
        'predicted_left_rms_error_db': l_rms,
        'predicted_right_rms_error_db': r_rms,
        'predicted_left_max_error_db': l_max,
        'predicted_right_max_error_db': r_max,
        'hearing_compensation_applied': True,
        'hearing_profile_summary': {
            'tested_at': profile.tested_at,
            'asymmetric_freqs': profile.asymmetric_freqs,
        },
        'filter_budget': {
            'family': filter_budget.family,
            'max_filters': filter_budget.max_filters,
            'fill_policy': filter_budget.fill_policy,
            'profile': filter_budget.profile,
        },
        'left_bands': [asdict(b) for b in left_bands],
        'right_bands': [asdict(b) for b in right_bands],
        'hearing_eq_points': {
            'left': {str(f): g for f, g in left_comp.items()},
            'right': {str(f): g for f, g in right_comp.items()},
        },
    }
    clipping_assessment = assess_eq_clipping(freqs, sample_rate, left_bands, right_bands)
    report['eq_clipping'] = {
        'will_clip': clipping_assessment.will_clip,
        'left_peak_boost_db': clipping_assessment.left_peak_boost_db,
        'right_peak_boost_db': clipping_assessment.right_peak_boost_db,
        'preamp_db': clipping_assessment.total_preamp_db,
        'headroom_loss_db': clipping_assessment.headroom_loss_db,
        'quality_concern': clipping_assessment.quality_concern,
    }
    return left_bands, right_bands, report


def _write_hearing_fit_readme(out_dir: Path, report: dict) -> None:
    target = report.get('target', 'flat')
    l_rms = report.get('predicted_left_rms_error_db', 0.0)
    r_rms = report.get('predicted_right_rms_error_db', 0.0)
    lines = [
        "headmatch hearing-fit results",
        "==============================",
        "",
        "Generated by headmatch from a hearing profile only (no headphone measurement).",
        "The EQ target is: target curve + hearing compensation (half-gain rule, Lybarger 1944).",
        f"Target curve: {target}",
        f"Predicted residual: L {l_rms:.2f} dB RMS, R {r_rms:.2f} dB RMS",
        "",
        "Files",
        "-----",
        "- equalizer_apo.txt: Equalizer APO parametric preset.",
        "- equalizer_apo_graphiceq.txt: GraphicEQ-format preset.",
        "- camilladsp_full.yaml: Full CamillaDSP config template.",
        "- camilladsp_filters_only.yaml: Filters-only CamillaDSP snippet.",
        "- hearing_fit_report.json: Full fit details and filter band list.",
        "",
        "Notes",
        "-----",
        "- This preset assumes a flat headphone frequency response.",
        "- For a more accurate result, measure your headphones and use --with-hearing-compensation.",
        "- Re-run the hearing test periodically or when your volume setting changes.",
    ]
    (out_dir / RESULTS_GUIDE_NAME).write_text('\n'.join(lines) + '\n', encoding="utf-8")


def run_hearing_fit(
    profile,
    out_dir: str | Path,
    sample_rate: int = 48000,
    target_path: str | Path | None = None,
    max_filters: int = 8,
    *,
    filter_budget: FilterBudget | None = None,
) -> dict:
    """
    Equipment-free EQ pipeline: hearing profile → ready-to-load EQ preset files.

    Writes equalizer_apo.txt, camilladsp_full.yaml, camilladsp_filters_only.yaml,
    equalizer_apo_graphiceq.txt, hearing_fit_report.json, and README.txt to out_dir.
    Returns the fit report dict.
    """
    from .exporters import (
        export_camilladsp_filter_snippet_yaml,
        export_camilladsp_filters_yaml,
        export_equalizer_apo_graphiceq_txt,
        export_equalizer_apo_parametric_txt,
    )
    from .signals import geometric_log_grid

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()

    left_bands, right_bands, report = fit_from_hearing_profile(
        profile, sample_rate, target_path=target_path,
        max_filters=max_filters, filter_budget=filter_budget,
    )

    # Per-channel preamp (preamp_db=None): a channel with no boost is not attenuated,
    # so a one-eared correction doesn't shift L/R balance.
    export_equalizer_apo_parametric_txt(
        out_dir / 'equalizer_apo.txt',
        left_bands,
        right_bands,
    )
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', left_bands, right_bands, samplerate=sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)

    # GraphicEQ rendered from the fitted bands onto the standard 127-point grid
    # (unified across all fitting workflows; EasyEffects/APO-safe).
    from .signals import standard_graphic_eq_grid
    gq_freqs = standard_graphic_eq_grid()
    export_equalizer_apo_graphiceq_txt(
        out_dir / 'equalizer_apo_graphiceq.txt',
        gq_freqs,
        peq_chain_response_db(gq_freqs, sample_rate, left_bands),
        peq_chain_response_db(gq_freqs, sample_rate, right_bands),
        comment='; GraphicEQ rendered on the standard 127-point grid from the fitted bands.',
    )

    # Drop a copy of the raw hearing profile alongside the EQ artifacts for
    # traceability (the canonical copy still lives in the config dir).
    if hasattr(profile, 'to_dict'):
        save_json(out_dir / 'hearing_profile.json', profile.to_dict())
    save_json(out_dir / 'hearing_fit_report.json', report)
    # run_summary.json so the hearing fit is discoverable in the Results/history
    # view and A/B-comparable, like the measurement fit.
    save_json(out_dir / 'run_summary.json',
              _hearing_run_summary(profile, out_dir, left_bands, right_bands, report, sample_rate, filter_budget).to_dict())
    _write_hearing_fit_readme(out_dir, report)

    return report


def _hearing_run_summary(profile, out_dir, left_bands, right_bands, report, sample_rate, filter_budget):
    from .contracts import (
        RUN_SUMMARY_SCHEMA_VERSION, ConfidenceSummary, FrontendRunSummary,
        RunErrorSummary, RunFilterCounts,
    )
    from .hearing_test import TEST_FREQUENCIES

    sides = list(profile.left.values()) + list(profile.right.values())
    total = len(sides)
    determined = sum(1 for t in sides if getattr(t, 'determined', False))
    floored = sum(1 for t in sides if getattr(t, 'floored', False))
    if floored:
        label, score, headline = "low", 30, "Some frequencies floored — volume likely too high; re-test at a lower level."
    elif total and determined == total:
        label, score, headline = "high", 80, "All frequencies measured (hearing-only fit; flat headphone assumed)."
    elif total and determined >= 0.6 * total:
        label, score, headline = "medium", 60, "Most frequencies measured (hearing-only fit)."
    else:
        label, score, headline = "low", 40, "Few frequencies converged — results uncertain; re-test."

    confidence = ConfidenceSummary(
        score=score, label=label, headline=headline,
        interpretation="Equipment-free hearing-based EQ. Not a clinical audiogram (uncalibrated, relative test).",
        reasons=(f"{determined}/{total} thresholds determined",),
        warnings=("Volume too high during the test — re-test at a lower level.",) if floored else (),
        metrics={"determined": float(determined), "floored": float(floored), "total": float(total)},
    )
    clipping = report.get('eq_clipping') if isinstance(report.get('eq_clipping'), dict) else None
    return FrontendRunSummary(
        schema_version=RUN_SUMMARY_SCHEMA_VERSION,
        generated_by=get_app_identity().as_metadata(),
        kind="fit",
        out_dir=str(out_dir),
        sample_rate=sample_rate,
        frequency_points=len(TEST_FREQUENCIES),
        target=report.get('target', 'flat'),
        filters=RunFilterCounts(left=len(left_bands), right=len(right_bands)),
        predicted_error_db=RunErrorSummary(
            left_rms=report['predicted_left_rms_error_db'],
            right_rms=report['predicted_right_rms_error_db'],
            left_max=report['predicted_left_max_error_db'],
            right_max=report['predicted_right_max_error_db'],
        ),
        confidence=confidence,
        plots={},
        results_guide=str(out_dir / 'README.txt'),
        filter_budget=filter_budget,
        eq_clipping_assessment=clipping,
    )


def _average_measurements(results: list[MeasurementResult]) -> MeasurementResult:
    """Average multiple measurement results into a single combined result."""
    left_db = np.mean([r.left_db for r in results], axis=0)
    right_db = np.mean([r.right_db for r in results], axis=0)
    left_raw_db = np.mean([r.left_raw_db for r in results], axis=0)
    right_raw_db = np.mean([r.right_raw_db for r in results], axis=0)
    avg_diagnostics: Dict[str, float] = {}
    all_keys = set().union(*(r.diagnostics.keys() for r in results))
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
    hearing_profile=None,
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
        left_bands, right_bands, report = fit_from_measurement(averaged, target_curve, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget, hearing_profile=hearing_profile)  # type: ignore[arg-type]
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
            left_bands, right_bands, report = fit_from_measurement(result, target_curve, sweep_spec.sample_rate, max_filters=max_filters, filter_budget=filter_budget, hearing_profile=hearing_profile)  # type: ignore[arg-type]
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
