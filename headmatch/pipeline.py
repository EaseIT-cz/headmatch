from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .analysis import MeasurementResult, analyze_measurement
from .app_identity import get_app_identity
from .contracts import RUN_SUMMARY_SCHEMA_VERSION
from .exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_parametric_txt,
)
from .io_utils import save_fr_csv, save_json
from .measure import MeasurementPaths, PipeWireDeviceConfig, run_pipewire_measurement
from .peq import PEQBand, fit_peq, peq_chain_response_db
from .plots import render_fit_graphs
from .signals import SweepSpec
from .targets import TargetCurve, create_flat_target, load_curve, resample_curve, clone_target_from_source_target


RESULTS_GUIDE_NAME = 'README.txt'


@dataclass
class IterationSummary:
    iteration: int
    left_rms_error_db: float
    right_rms_error_db: float
    left_max_error_db: float
    right_max_error_db: float



def _confidence_penalty(value: float, good: float, bad: float) -> float:
    if value <= good:
        return 0.0
    if value >= bad:
        return 1.0
    return float((value - good) / max(bad - good, 1e-9))



def _summarize_trustworthiness(result: MeasurementResult, report: dict) -> dict:
    diagnostics = result.diagnostics
    roughness = max(diagnostics['left_roughness_db'], diagnostics['right_roughness_db'])
    predicted_rms = max(report['predicted_left_rms_error_db'], report['predicted_right_rms_error_db'])
    predicted_max = max(report['predicted_left_max_error_db'], report['predicted_right_max_error_db'])

    penalties = {
        'alignment': _confidence_penalty(1.0 - diagnostics['alignment_reference_score'], 0.20, 0.40),
        'alignment_peak': _confidence_penalty(1.0 - diagnostics['alignment_peak_ratio'], 0.15, 0.35),
        'channel_mismatch': _confidence_penalty(diagnostics['channel_mismatch_rms_db'], 0.8, 2.5),
        'roughness': _confidence_penalty(roughness, 0.3, 1.5),
        'residual_rms': _confidence_penalty(predicted_rms, 2.0, 4.5),
        'residual_peak': _confidence_penalty(predicted_max, 4.0, 9.0),
    }
    penalty_points = (
        penalties['alignment'] * 10
        + penalties['alignment_peak'] * 8
        + penalties['channel_mismatch'] * 36
        + penalties['roughness'] * 28
        + penalties['residual_rms'] * 12
        + penalties['residual_peak'] * 6
    )
    score = max(0, min(100, int(round(100 - penalty_points))))

    warnings: list[str] = []
    if diagnostics['alignment_reference_score'] < 0.80:
        warnings.append('Alignment to the sweep was weaker than expected, so the measurement timing may be unreliable.')
    if diagnostics['alignment_peak_ratio'] < 0.85:
        warnings.append('The sweep alignment peak was not clearly dominant, which can happen with extra noise or confusing echoes.')
    if diagnostics['channel_mismatch_rms_db'] >= 0.8:
        warnings.append('Left and right measurements differ more than usual, which often means the headset or microphones were not seated consistently.')
    if roughness >= 0.3:
        warnings.append('The raw trace is rougher than expected, suggesting noise, movement, or a leaky seal during capture.')
    if predicted_rms >= 2.0:
        warnings.append('The fitted result still leaves noticeable residual error, so the generated EQ should be treated as provisional.')
    if predicted_max >= 4.0:
        warnings.append('Some frequencies still miss the target by a wide margin, so inspect the graphs before trusting the preset.')

    if score >= 85:
        label = 'high'
        headline = 'This run looks trustworthy.'
        interpretation = 'The measurement aligned cleanly, the channels agree reasonably well, and the predicted post-EQ error is low enough for normal use.'
    elif score >= 65:
        label = 'medium'
        headline = 'This run looks usable, but review it before trusting it fully.'
        interpretation = 'Nothing looks catastrophically wrong, but one or more stability signals are only fair. Check the graphs and consider re-running if the sound seems off.'
    else:
        label = 'low'
        headline = 'This run looks suspicious.'
        interpretation = 'One or more stability signals suggest the measurement or fit may not be trustworthy. Re-seat the headphones or microphones and capture another run before relying on this EQ.'

    reasons = [
        f"Alignment score: {diagnostics['alignment_reference_score']:.3f} (higher is better).",
        f"Alignment peak clarity: {diagnostics['alignment_peak_ratio']:.3f}.",
        f"Channel mismatch: {diagnostics['channel_mismatch_rms_db']:.2f} dB RMS.",
        f"Trace roughness: L {diagnostics['left_roughness_db']:.2f} dB, R {diagnostics['right_roughness_db']:.2f} dB.",
        f"Predicted residual error: {predicted_rms:.2f} dB RMS, {predicted_max:.2f} dB max.",
    ]

    return {
        'score': score,
        'label': label,
        'headline': headline,
        'interpretation': interpretation,
        'reasons': reasons,
        'warnings': warnings,
        'metrics': {
            'alignment_reference_score': diagnostics['alignment_reference_score'],
            'alignment_peak_ratio': diagnostics['alignment_peak_ratio'],
            'channel_mismatch_rms_db': diagnostics['channel_mismatch_rms_db'],
            'left_roughness_db': diagnostics['left_roughness_db'],
            'right_roughness_db': diagnostics['right_roughness_db'],
            'capture_rms_dbfs': diagnostics['capture_rms_dbfs'],
            'predicted_rms_error_db': predicted_rms,
            'predicted_max_error_db': predicted_max,
        },
    }



def write_results_guide(out_dir: Path, kind: str, trust_summary: dict | None = None) -> Path:
    if kind == 'fit':
        title = 'headmatch fit results'
        overview = 'This folder contains one analyzed recording and the EQ files built from it.'
        files = [
            ('run_summary.json', 'Plain-language machine-readable summary of the run, trust score, warnings, and predicted error after EQ.'),
            ('fit_report.json', 'Detailed PEQ band list plus diagnostics used to judge whether the fit looks trustworthy.'),
            ('equalizer_apo.txt', 'Ready-to-load Equalizer APO preset file for this result.'),
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
            'Use equalizer_apo.txt for Equalizer APO, or use the CamillaDSP YAML files for CamillaDSP.',
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
            ('equalizer_apo.txt', 'Equalizer APO preset file for this iteration.'),
            ('camilladsp_full.yaml', 'Full CamillaDSP config template for this iteration.'),
            ('camilladsp_filters_only.yaml', 'Filters-only CamillaDSP snippet for this iteration.'),
            ('measurement_left.csv', 'Estimated left-channel response for this iteration.'),
            ('measurement_right.csv', 'Estimated right-channel response for this iteration.'),
            ('fit_overview.svg', 'Two-panel SVG graph comparing raw measurement, smoothed measurement, target curve, and predicted fitted result.'),
            ('fit_left.svg', 'Left-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
            ('fit_right.svg', 'Right-channel SVG graph for closer inspection of raw, measured, target, and fitted curves.'),
        ]
        next_steps = [
            'Use equalizer_apo.txt for Equalizer APO, or use the CamillaDSP YAML files for CamillaDSP.',
            'Compare this folder with the other iter_* folders if you want to see whether the predicted residual improved.',
            'Check the top-level iterations_summary.json for the per-iteration error overview.',
        ]

    lines = [title, '=' * len(title), '', overview]
    if trust_summary is not None:
        lines.extend([
            '',
            'Trust summary',
            '-------------',
            f"- Confidence: {trust_summary['label']} ({trust_summary['score']}/100)",
            f"- {trust_summary['headline']}",
            f"- {trust_summary['interpretation']}",
        ])
        if trust_summary['warnings']:
            lines.append('- Warnings:')
            for warning in trust_summary['warnings']:
                lines.append(f'  - {warning}')
    lines.extend(['', 'Files', '-----'])
    for name, description in files:
        lines.append(f'- {name}: {description}')
    lines.extend(['', 'Next steps', '----------'])
    for step in next_steps:
        lines.append(f'- {step}')
    path = out_dir / RESULTS_GUIDE_NAME
    path.write_text('\n'.join(lines) + '\n')
    return path



def _run_summary(kind: str, out_dir: Path, result: MeasurementResult, target: TargetCurve, left_bands: list[PEQBand], right_bands: list[PEQBand], report: dict, sample_rate: int) -> dict:
    identity = get_app_identity()
    target_resampled = resample_curve(target, result.freqs_hz)
    trust_summary = _summarize_trustworthiness(result, report)
    return {
        'schema_version': RUN_SUMMARY_SCHEMA_VERSION,
        'generated_by': identity.as_metadata(),
        'kind': kind,
        'out_dir': str(out_dir),
        'sample_rate': sample_rate,
        'frequency_points': int(len(result.freqs_hz)),
        'target': target_resampled.name,
        'filters': {
            'left': len(left_bands),
            'right': len(right_bands),
        },
        'predicted_error_db': {
            'left_rms': report['predicted_left_rms_error_db'],
            'right_rms': report['predicted_right_rms_error_db'],
            'left_max': report['predicted_left_max_error_db'],
            'right_max': report['predicted_right_max_error_db'],
        },
        'confidence': trust_summary,
        'plots': {
            'overview': str(out_dir / 'fit_overview.svg'),
            'left': str(out_dir / 'fit_left.svg'),
            'right': str(out_dir / 'fit_right.svg'),
        },
        'results_guide': str(out_dir / RESULTS_GUIDE_NAME),
    }


def _write_fit_artifacts(
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
) -> dict:
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', left_bands, right_bands, samplerate=sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)
    export_equalizer_apo_parametric_txt(out_dir / 'equalizer_apo.txt', left_bands, right_bands)
    if write_target_curve_csv:
        save_fr_csv(out_dir / 'target_curve.csv', result.freqs_hz, resample_curve(target, result.freqs_hz).values_db, 'target_db')
    render_fit_graphs(out_dir, result, target, sample_rate, left_bands, right_bands)
    summary = _run_summary(kind, out_dir, result, target, left_bands, right_bands, report, sample_rate)
    save_json(out_dir / 'fit_report.json', report)
    save_json(out_dir / 'run_summary.json', summary)
    write_results_guide(out_dir, kind=kind, trust_summary=summary['confidence'])
    return summary


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
    identity = get_app_identity()
    report = {
        'generated_by': identity.as_metadata(),
        'predicted_left_rms_error_db': l_rms,
        'predicted_right_rms_error_db': r_rms,
        'predicted_left_max_error_db': l_max,
        'predicted_right_max_error_db': r_max,
        'measurement_diagnostics': result.diagnostics,
        'left_bands': [asdict(b) for b in left_bands],
        'right_bands': [asdict(b) for b in right_bands],
    }
    report['confidence'] = _summarize_trustworthiness(result, report)
    return left_bands, right_bands, report



def process_single_measurement(recording_wav: str | Path, out_dir: str | Path, sweep_spec: SweepSpec, target_path: str | Path | None = None, max_filters: int = 8) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_measurement(recording_wav, sweep_spec, out_dir=out_dir)
    target = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
    left_bands, right_bands, report = fit_from_measurement(result, target, sweep_spec.sample_rate, max_filters=max_filters)
    _write_fit_artifacts(
        out_dir,
        kind='fit',
        result=result,
        target=target,
        left_bands=left_bands,
        right_bands=right_bands,
        report=report,
        sample_rate=sweep_spec.sample_rate,
        write_target_curve_csv=True,
    )
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
        run_summary = _write_fit_artifacts(
            iter_dir,
            kind='iteration',
            result=result,
            target=target_curve,
            left_bands=left_bands,
            right_bands=right_bands,
            report=report,
            sample_rate=sweep_spec.sample_rate,
            write_target_curve_csv=False,
        )
        predicted = run_summary['predicted_error_db']
        summaries.append(asdict(IterationSummary(i, predicted['left_rms'], predicted['right_rms'], predicted['left_max'], predicted['right_max'])))
    identity = get_app_identity()
    save_json(output_dir / 'iterations_summary.json', {'generated_by': identity.as_metadata(), 'iterations': summaries, 'count': len(summaries)})
    return summaries
