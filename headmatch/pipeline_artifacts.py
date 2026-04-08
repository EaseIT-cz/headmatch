"""Artifact writing for fit results — exports, graphs, summaries, README.

Extracted from pipeline.py (TASK-083). Contains the file-writing logic
shared by single-fit and iterative paths.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis import MeasurementResult
from .app_identity import get_app_identity
from .contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
    RUN_SUMMARY_SCHEMA_VERSION,
)
from .exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_graphiceq_txt,
    export_equalizer_apo_parametric_txt,
)
from .eq_clipping import EQClippingAssessment
from .io_utils import save_json
from .peq import FilterBudget, PEQBand, peq_chain_response_db
from .pipeline_confidence import summarize_trustworthiness
from .plots import render_fit_graphs
from .targets import TargetCurve, resample_curve
from .troubleshooting import confidence_troubleshooting_steps


RESULTS_GUIDE_NAME = 'README.txt'


def _resolve_target_values(result: MeasurementResult, target: TargetCurve) -> tuple[np.ndarray, np.ndarray]:
    """Resolve target curve to per-channel absolute values on the measurement grid."""
    target_resampled = resample_curve(target, result.freqs_hz)
    if target_resampled.semantics == 'relative':
        left_values = result.left_db + target_resampled.values_db
        right_values = result.right_db + target_resampled.values_db
    else:
        left_values = target_resampled.values_db
        right_values = target_resampled.values_db
    return left_values, right_values


def _run_summary(
    kind: str,
    out_dir: Path,
    result: MeasurementResult,
    target: TargetCurve,
    left_bands: list[PEQBand],
    right_bands: list[PEQBand],
    report: dict,
    sample_rate: int,
    filter_budget: FilterBudget,
) -> FrontendRunSummary:
    identity = get_app_identity()
    trust_summary = summarize_trustworthiness(result, report)
    clipping_payload = report.get('eq_clipping')
    return FrontendRunSummary(
        schema_version=RUN_SUMMARY_SCHEMA_VERSION,
        generated_by=identity.as_metadata(),
        kind=kind,
        out_dir=str(out_dir),
        sample_rate=sample_rate,
        frequency_points=int(len(result.freqs_hz)),
        target=target.name,
        filters=RunFilterCounts(left=len(left_bands), right=len(right_bands)),
        predicted_error_db=RunErrorSummary(
            left_rms=report['predicted_left_rms_error_db'],
            right_rms=report['predicted_right_rms_error_db'],
            left_max=report['predicted_left_max_error_db'],
            right_max=report['predicted_right_max_error_db'],
        ),
        confidence=trust_summary,
        plots={
            'overview': str(out_dir / 'fit_overview.svg'),
            'left': str(out_dir / 'fit_left.svg'),
            'right': str(out_dir / 'fit_right.svg'),
        },
        results_guide=str(out_dir / RESULTS_GUIDE_NAME),
        filter_budget=filter_budget,
        eq_clipping_assessment=clipping_payload if isinstance(clipping_payload, dict) else None,
    )


def _write_fixed_band_graphiceq_artifact(
    out_dir: Path,
    *,
    left_bands: list[PEQBand],
    right_bands: list[PEQBand],
    filter_budget: FilterBudget,
) -> None:
    if filter_budget.family != 'graphic_eq':
        return
    export_equalizer_apo_graphiceq_txt(
        out_dir / 'equalizer_apo_fixed_graphiceq.txt',
        [band.freq for band in left_bands],
        [band.gain_db for band in left_bands],
        [band.gain_db for band in right_bands],
        comment='; Generated directly from the fixed-band GraphicEQ fitting backend.',
    )


def write_results_guide(out_dir: Path, kind: str, trust_summary: ConfidenceSummary | None = None) -> Path:
    """Write a human-readable README.txt explaining the output folder contents."""
    if kind == 'fit':
        title = 'headmatch fit results'
        overview = 'This folder contains one analyzed recording and the EQ files built from it.'
        files = [
            ('run_summary.json', 'Plain-language machine-readable summary of the run, trust score, warnings, and predicted error after EQ.'),
            ('fit_report.json', 'Detailed PEQ band list plus diagnostics used to judge whether the fit looks trustworthy.'),
            ('equalizer_apo.txt', 'Ready-to-load Equalizer APO parametric preset file for this result.'),
            ('equalizer_apo_graphiceq.txt', 'Equalizer APO GraphicEQ-format preset built from the shared effective correction target.'),
            ('equalizer_apo_fixed_graphiceq.txt', 'Direct fixed-band GraphicEQ fit when the GraphicEQ backend family is selected.'),
            ('camilladsp_full.yaml', 'Full CamillaDSP config template. Replace the capture/playback device placeholders before use.'),
            ('camilladsp_filters_only.yaml', 'Filters and pipeline only, for merging into an existing CamillaDSP config.'),
            ('target_curve.csv', 'The target curve actually used for fitting on the analysis frequency grid.'),
            ('measurement_left.csv', 'Estimated left-channel headphone response from the recording.'),
            ('measurement_right.csv', 'Estimated right-channel headphone response from the recording.'),
            ('fit_overview.svg', 'Two-panel SVG graph comparing raw measurement, smoothed measurement, target curve, and predicted fitted result.'),
            ('fit_left.svg', 'Left-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
            ('fit_right.svg', 'Right-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
        ]
        next_steps = [
            'Open run_summary.json first if you want the quickest overview, including the trust/confidence summary.',
            'Use equalizer_apo.txt for Equalizer APO parametric filters, equalizer_apo_graphiceq.txt for the dense shared-target GraphicEQ export, equalizer_apo_fixed_graphiceq.txt for direct fixed-band GraphicEQ fits, or the CamillaDSP YAML files for CamillaDSP.',
            'If the result still looks off, repeat the measurement with a fresh reseat before adding more filters.',
        ]
    else:
        title = 'headmatch iteration results'
        overview = 'This folder contains one measurement-and-fit pass inside a multi-iteration run.'
        files = [
            ('sweep.wav', 'The sweep played during this iteration.'),
            ('recording.wav', 'The recorded response captured for this iteration.'),
            ('run_summary.json', 'Summary of this iteration, including trust/confidence cues and predicted error after EQ.'),
            ('fit_report.json', 'Detailed PEQ band list plus diagnostics used to judge whether this iteration looks trustworthy.'),
            ('equalizer_apo.txt', 'Equalizer APO parametric preset file for this iteration.'),
            ('equalizer_apo_graphiceq.txt', 'Equalizer APO GraphicEQ-format preset for this iteration.'),
            ('equalizer_apo_fixed_graphiceq.txt', 'Direct fixed-band GraphicEQ fit for this iteration when that backend family is selected.'),
            ('camilladsp_full.yaml', 'Full CamillaDSP config template for this iteration.'),
            ('camilladsp_filters_only.yaml', 'Filters-only CamillaDSP snippet for this iteration.'),
            ('measurement_left.csv', 'Estimated left-channel response for this iteration.'),
            ('measurement_right.csv', 'Estimated right-channel response for this iteration.'),
            ('fit_overview.svg', 'Two-panel SVG graph comparing raw measurement, smoothed measurement, target curve, and predicted fitted result.'),
            ('fit_left.svg', 'Left-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
            ('fit_right.svg', 'Right-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
        ]
        next_steps = [
            'Use equalizer_apo.txt for Equalizer APO parametric filters, equalizer_apo_graphiceq.txt for the dense shared-target GraphicEQ export, equalizer_apo_fixed_graphiceq.txt for direct fixed-band GraphicEQ fits, or the CamillaDSP YAML files for CamillaDSP.',
            'Compare this folder with the other iter_* folders if you want to see whether the predicted residual improved.',
            'Check the top-level iterations_summary.json for the per-iteration error overview.',
        ]

    lines = [title, '=' * len(title), '', overview]
    if trust_summary is not None:
        lines.extend([
            '',
            'Trust summary',
            '-------------',
            f"- Confidence: {trust_summary.label} ({trust_summary.score}/100)",
            f"- {trust_summary.headline}",
            f"- {trust_summary.interpretation}",
        ])
        if trust_summary.warnings:
            lines.append('- Warnings:')
            for warning in trust_summary.warnings:
                lines.append(f'  - {warning}')
        troubleshooting = confidence_troubleshooting_steps(trust_summary)
        if troubleshooting:
            lines.append('- What to try next:')
            for step in troubleshooting:
                lines.append(f'  - {step}')
    lines.extend(['', 'Files', '-----'])
    for name, description in files:
        lines.append(f'- {name}: {description}')
    lines.extend(['', 'Next steps', '----------'])
    for step in next_steps:
        lines.append(f'- {step}')
    path = out_dir / RESULTS_GUIDE_NAME
    path.write_text('\n'.join(lines) + '\n', encoding="utf-8")
    return path


def write_fit_artifacts(
    out_dir: Path,
    *,
    kind: str,
    result: MeasurementResult,
    target: TargetCurve,
    left_bands: list[PEQBand],
    right_bands: list[PEQBand],
    report: dict,
    sample_rate: int,
    write_target_curve_csv: bool,
    filter_budget: FilterBudget,
) -> dict:
    """Write all fit output artifacts to out_dir and return the run summary dict."""
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', left_bands, right_bands, samplerate=sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)
    clipping = report.get('eq_clipping') if isinstance(report.get('eq_clipping'), dict) else None
    export_equalizer_apo_parametric_txt(
        out_dir / 'equalizer_apo.txt',
        left_bands,
        right_bands,
        preamp_db=(float(clipping['preamp_db']) if clipping and clipping.get('will_clip') else None),
    )
    # Dense GraphicEQ: export the actual PEQ-fitted response (what the parametric
    # preset applies), not the raw correction target.
    left_fitted_eq = peq_chain_response_db(result.freqs_hz, sample_rate, left_bands)
    right_fitted_eq = peq_chain_response_db(result.freqs_hz, sample_rate, right_bands)
    export_equalizer_apo_graphiceq_txt(
        out_dir / 'equalizer_apo_graphiceq.txt',
        result.freqs_hz,
        left_fitted_eq,
        right_fitted_eq,
    )
    _write_fixed_band_graphiceq_artifact(
        out_dir,
        left_bands=left_bands,
        right_bands=right_bands,
        filter_budget=filter_budget,
    )
    if write_target_curve_csv:
        left_target, right_target = _resolve_target_values(result, target)
        lines = ['frequency_hz,left_target_db,right_target_db']
        for freq, left, right in zip(result.freqs_hz, left_target, right_target):
            lines.append(f'{float(freq)},{float(left)},{float(right)}')
        (out_dir / 'target_curve.csv').write_text('\n'.join(lines) + '\n', encoding="utf-8")
    render_fit_graphs(out_dir, result, target, sample_rate, left_bands, right_bands)
    summary = _run_summary(kind, out_dir, result, target, left_bands, right_bands, report, sample_rate, filter_budget)
    save_json(out_dir / 'fit_report.json', report)
    save_json(out_dir / 'run_summary.json', summary.to_dict())
    write_results_guide(out_dir, kind=kind, trust_summary=summary.confidence)
    return summary.to_dict()
