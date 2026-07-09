"""Room measurement and modal correction orchestration.

This module provides target curve construction and PEQ fitting for room
measurements with calibrated USB microphones, producing bass-only
corrective EQ (≤ cutoff Hz).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .analysis import MeasurementResult, analyze_room_measurement
from .app_identity import get_app_identity
from .contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
    RUN_SUMMARY_SCHEMA_VERSION,
)
from .eq_clipping import assess_eq_clipping
from .exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_parametric_txt,
)
from .io_utils import save_fr_csv, save_json
from .mic_cal import MicCalibration, calibration_offset, load_mic_calibration
from .peq import PEQBand, fit_peq, peq_chain_response_db, FilterBudget
from .pipeline_confidence import summarize_trustworthiness
from .plots import render_fit_graphs
from .signals import (
    SweepSpec,
    fractional_octave_smoothing,
    geometric_log_grid,
    standard_graphic_eq_grid,
)
from .targets import TargetCurve, create_flat_target, resample_curve


# Constants from TASK-117
ROOM_CUTOFF_DEFAULT_HZ = 300.0
ROOM_MAX_BOOST_DB = 2.0
ROOM_LOW_FREQ_Q_CAP = 12.0


@dataclass
class RoomFitResult:
    """Result of room measurement fitting.
    
    Attributes:
        result: MeasurementResult with room frequency response
        eq_bands: PEQ bands for correction
        target: Target curve used
        fit_report: Detailed fitting report
        run_summary: FrontendRunSummary dict
        out_dir: Output directory path
        warnings: List of warning messages
    """
    result: MeasurementResult
    eq_bands: list[PEQBand]
    target: TargetCurve
    fit_report: dict[str, Any]
    run_summary: dict[str, Any]
    out_dir: Path
    warnings: list[str]


def build_room_target(
    freqs_hz: np.ndarray,
    sub_bass_rolloff: bool = True,
) -> TargetCurve:
    """Build a flat room target curve through the modal band.
    
    Returns a flat (0 dB) curve with optional ~2-3 dB rolloff below ~40 Hz
    to account for typical room measurement floor noise and mic limitations.
    
    Args:
        freqs_hz: Frequency grid for the target
        sub_bass_rolloff: If True, apply gentle rolloff below 40 Hz
        
    Returns:
        TargetCurve with room-appropriate target values
    """
    values_db = np.zeros_like(freqs_hz, dtype=np.float64)
    
    if sub_bass_rolloff:
        # Apply ~2-3 dB rolloff below 40 Hz using gentle slope
        # At 20 Hz: ~-2.5 dB, at 40 Hz: 0 dB, linear interpolation in log domain
        rolloff_freqs = freqs_hz <= 40.0
        if np.any(rolloff_freqs):
            # Simple linear rolloff: -2.5 dB at 20 Hz, 0 dB at 40 Hz
            rolloff_db = -2.5 * (1.0 - np.interp(
                freqs_hz[rolloff_freqs], [20.0, 40.0], [0.0, 1.0]
            ))
            values_db[rolloff_freqs] = rolloff_db
    
    return TargetCurve(freqs_hz, values_db, name='room_modal_flat', semantics='absolute')


def fit_room_bands(
    freqs_hz: np.ndarray,
    eq_target_db: np.ndarray,
    sample_rate: int,
    cutoff_hz: float,
    max_boost_db: float = ROOM_MAX_BOOST_DB,
    low_freq_q_cap: float = ROOM_LOW_FREQ_Q_CAP,
) -> list[PEQBand]:
    """Fit PEQ bands for room correction with band-limiting and boost constraints.
    
    Pure core function that wraps fit_peq with room-specific constraints:
    - Band-limit: no filter above cutoff_hz (structural: data filtered before fitting)
    - Boost ceiling: max_boost_db enforced structurally
    - Narrow mode support: Q cap for sub-100 Hz
    
    Args:
        freqs_hz: Frequency grid in Hz
        eq_target_db: EQ target (desired response) in dB
        sample_rate: Sample rate
        cutoff_hz: Maximum frequency for fitted bands
        max_boost_db: Maximum allowed boost (positive gain)
        low_freq_q_cap: Maximum Q for low frequencies (< 120 Hz)
        
    Returns:
        List of fitted PEQ bands
    """
    # Structural cutoff: filter data ABOVE cutoff Hz before fitting.
    # This ensures the residual/error signal does not see above-cutoff frequencies.
    mask = freqs_hz <= cutoff_hz * 1.1  # Include small margin (10% above) for edge effects
    fit_freqs_hz = freqs_hz[mask]
    fit_eq_target_db = eq_target_db[mask]

    bands = fit_peq(
        fit_freqs_hz,
        fit_eq_target_db,
        sample_rate,
        max_filters=8,
        max_gain_db=12.0,  # Max cut depth
        max_q=12.0,
        max_freq_hz=cutoff_hz,
        low_freq_q_cap=low_freq_q_cap,
        max_boost_db=max_boost_db,
    )
    return bands


def _energy_average_responses(
    result1: MeasurementResult,
    result2: MeasurementResult,
) -> MeasurementResult:
    """Energy-average two room measurement responses (magnitude-domain average).
    
    Converts dB to linear magnitude, averages, converts back to dB.
    """
    # Convert dB to linear magnitude (power = 10^(db/10))
    left1_mag = 10 ** (result1.left_db / 10.0)
    left2_mag = 10 ** (result2.left_db / 10.0)
    right1_mag = 10 ** (result1.right_db / 10.0)
    right2_mag = 10 ** (result2.right_db / 10.0)
    
    left_raw1_mag = 10 ** (result1.left_raw_db / 10.0)
    left_raw2_mag = 10 ** (result2.left_raw_db / 10.0)
    right_raw1_mag = 10 ** (result1.right_raw_db / 10.0)
    right_raw2_mag = 10 ** (result2.right_raw_db / 10.0)
    
    # Energy average: sqrt of mean of squared magnitudes (power average)
    left_avg = 0.5 * (left1_mag + left2_mag)
    right_avg = 0.5 * (right1_mag + right2_mag)
    left_raw_avg = 0.5 * (left_raw1_mag + left_raw2_mag)
    right_raw_avg = 0.5 * (right_raw1_mag + right_raw2_mag)
    
    # Convert back to dB
    left_db = 10 * np.log10(left_avg + 1e-12)
    right_db = 10 * np.log10(right_avg + 1e-12)
    left_raw_db = 10 * np.log10(left_raw_avg + 1e-12)
    right_raw_db = 10 * np.log10(right_raw_avg + 1e-12)
    
    # Merge diagnostics: use result1 but flag that this is averaged
    diagnostics = dict(result1.diagnostics)
    diagnostics['two_position_averaged'] = True
    
    return MeasurementResult(
        freqs_hz=result1.freqs_hz.copy(),
        left_db=left_db,
        right_db=right_db,
        left_raw_db=left_raw_db,
        right_raw_db=right_raw_db,
        diagnostics=diagnostics,
    )


def _assess_room_fit_quality(
    result: MeasurementResult,
    eq_bands: list[PEQBand],
    cutoff_hz: float,
) -> dict:
    """Assess the quality of the room fit and generate warnings."""
    warnings = []
    
    # Check for single-point measurement caveats
    if not result.diagnostics.get('two_position_averaged', False):
        warnings.append(
            "Single-point room measurement. Modal response varies with position. "
            "Consider averaging measurements from two or more listening positions."
        )
    
    # Check for sub-cutoff issues
    min_freq = float(np.min(result.freqs_hz))
    if min_freq > 30.0:
        warnings.append(
            f"Low-frequency measurement starts at {min_freq:.1f} Hz. "
            "Room mode resolution below this frequency is limited."
        )
    
    # Channel mismatch check (should be 0 for mono, but check anyway)
    channel_mismatch = result.diagnostics.get('channel_mismatch_rms_db', 0.0)
    
    # EQ boost assessment
    if eq_bands:
        eq_response = peq_chain_response_db(result.freqs_hz, 48000, eq_bands)
        max_boost = float(np.max(eq_response))
        max_cut = float(np.min(eq_response))
    else:
        max_boost = 0.0
        max_cut = 0.0
    
    return {
        'warnings': warnings,
        'max_boost_db': max_boost,
        'max_cut_db': max_cut,
        'cutoff_hz': cutoff_hz,
        'channel_mismatch_rms_db': channel_mismatch,
    }


def _write_room_results_guide(
    out_dir: Path,
    eq_bands: list[PEQBand],
    trust_summary: ConfidenceSummary | None,
    warnings: list[str],
) -> Path:
    """Write human-readable README.txt for room fit results."""
    lines = [
        'headmatch room measurement results',
        '================================',
        '',
        'This folder contains the room measurement and EQ correction files.',
        '',
        'Files',
        '-----',
        ('room_fr.csv', 'Measured room frequency response (calibrated, averaged if two positions).'),
        ('target_curve.csv', 'The target curve used for fitting (flat through modal band).'),
        ('equalizer_apo.txt', 'Equalizer APO parametric preset for room correction.'),
        ('camilladsp_full.yaml', 'Full CamillaDSP config template.'),
        ('camilladsp_filters_only.yaml', 'Filters-only snippet for existing config.'),
        ('fit_overview.svg', 'Room fit graph with cutoff marker.'),
        ('run_summary.json', 'Machine-readable summary of the run.'),
        ('fit_report.json', 'Detailed PEQ band list and diagnostics.'),
        ('README.txt', 'This file.'),
    ]
    
    lines.append('')
    lines.append('Room-specific notes')
    lines.append('-------------------')
    
    if warnings:
        lines.append('Warnings:')
        for w in warnings:
            lines.append(f'  - {w}')
    else:
        lines.append('No warnings.')
    
    if trust_summary:
        lines.append('')
        lines.append('Trust Summary:')
        lines.append(f"  Confidence: {trust_summary.label} ({trust_summary.score}/100)")
        lines.append(f"  Headline: {trust_summary.headline}")
    
    lines.append('')
    lines.append('Usage')
    lines.append('-----')
    lines.append('Load equalizer_apo.txt into Equalizer APO or')
    lines.append('use the CamillaDSP YAML files with your DSP setup.')
    lines.append('')
    lines.append('Note: This correction is only valid through the fitted cutoff frequency.')
    
    # Create entries list for the body of README
    content = ['headmatch room measurement results', '=' * 40, '']
    content.append('This folder contains the room measurement and EQ correction files.')
    content.append('')
    content.append('Files')
    content.append('-----')
    for name, desc in [
        ('room_fr.csv', 'Measured room frequency response (calibrated, averaged if two positions).'),
        ('target_curve.csv', 'The target curve used for fitting (flat through modal band).'),
        ('equalizer_apo.txt', 'Equalizer APO parametric preset for room correction.'),
        ('camilladsp_full.yaml', 'Full CamillaDSP config template.'),
        ('camilladsp_filters_only.yaml', 'Filters-only snippet for existing config.'),
        ('fit_overview.svg', 'Room fit graph with cutoff marker.'),
        ('run_summary.json', 'Machine-readable summary of the run.'),
        ('fit_report.json', 'Detailed PEQ band list and diagnostics.'),
        ('README.txt', 'This file.'),
    ]:
        content.append(f'- {name}: {desc}')
    
    content.append('')
    content.append('Room-specific notes')
    content.append('-------------------')
    
    if warnings:
        content.append('Warnings:')
        for w in warnings:
            content.append(f'  - {w}')
    else:
        content.append('No warnings.')
    
    if trust_summary:
        content.append('')
        content.append('Trust Summary:')
        content.append(f"  Confidence: {trust_summary.label} ({trust_summary.score}/100)")
        content.append(f"  Headline: {trust_summary.headline}")
    
    content.append('')
    content.append('Usage')
    content.append('-----')
    content.append('Load equalizer_apo.txt into Equalizer APO or')
    content.append('use the CamillaDSP YAML files with your DSP setup.')
    content.append('')
    content.append('Note: This correction is only valid through the fitted cutoff frequency.')
    
    path = out_dir / 'README.txt'
    path.write_text('\n'.join(content) + '\n', encoding='utf-8')
    return path


def run_room_fit(
    recording: str | Path,
    recording_two: str | Path | None,
    mic_cal: MicCalibration | None,
    cutoff_hz: float,
    max_boost_db: float,
    target_csv: str | Path | None,
    out_dir: str | Path,
) -> RoomFitResult:
    """Run full room measurement fitting workflow.
    
    Orchestrates the room measurement analysis, target building,
    PEQ fitting, and artifact generation.
    
    Args:
        recording: Path to primary room measurement WAV file
        recording_two: Optional path to second position measurement for averaging
        mic_cal: Optional microphone calibration (applies calibration_offset)
        cutoff_hz: Maximum frequency for EQ correction
        max_boost_db: Maximum allowed boost (typically ROOM_MAX_BOOST_DB=2.0)
        target_csv: Optional custom target CSV path (uses flat target if None)
        out_dir: Output directory for results
        
    Returns:
        RoomFitResult with all outputs and metadata
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    fit_warnings: list[str] = []
    
    # Validate mic_cal - warn if missing
    if mic_cal is None:
        warnings.warn(
            "No microphone calibration provided. Measurement may be inaccurate. "
            "Consider using a calibration file for best results.",
            UserWarning
        )
        fit_warnings.append(
            "No microphone calibration: measurement accuracy is unverified."
        )
    
    # Analyze room measurement(s)
    sweep_spec = SweepSpec(
        sample_rate=48000,
        duration_s=8.0,
        f_start=20.0,
        f_end=20000.0,
        pre_silence_s=0.5,
        post_silence_s=1.0,
        amplitude=0.2,
    )
    
    result1 = analyze_room_measurement(recording, sweep_spec, out_dir=None)
    
    # Energy-average two recordings if provided
    if recording_two is not None:
        result2 = analyze_room_measurement(recording_two, sweep_spec, out_dir=None)
        result = _energy_average_responses(result1, result2)
    else:
        result = result1
    
    # Apply mic calibration offset if provided
    if mic_cal is not None:
        offset_db = calibration_offset(mic_cal, result.freqs_hz)
        result = MeasurementResult(
            freqs_hz=result.freqs_hz,
            left_db=result.left_db - offset_db,
            right_db=result.right_db - offset_db,
            left_raw_db=result.left_raw_db - offset_db,
            right_raw_db=result.right_raw_db - offset_db,
            diagnostics=result.diagnostics,
        )
    
    # Build or load target
    if target_csv is not None:
        from .targets import load_curve
        target = load_curve(target_csv)
        target = resample_curve(target, result.freqs_hz)
    else:
        target = build_room_target(result.freqs_hz, sub_bass_rolloff=True)
    
    # Build EQ target: measured + target = desired
    # For room: measured + eq = target => eq_target = target - measured
    eq_target_db = target.values_db - result.left_db
    
    # Fit room bands with constraints
    sample_rate = 48000
    bands = fit_room_bands(
        result.freqs_hz,
        eq_target_db,
        sample_rate,
        cutoff_hz=cutoff_hz,
        max_boost_db=max_boost_db,
        low_freq_q_cap=ROOM_LOW_FREQ_Q_CAP,
    )
    
    # Duplicate for stereo (mono room measurement uses same EQ for both channels)
    eq_bands = bands
    
    # Assess fit quality and generate warnings
    quality_assessment = _assess_room_fit_quality(result, eq_bands, cutoff_hz)
    fit_warnings.extend(quality_assessment['warnings'])
    
    # Compute predicted error
    eq_response = peq_chain_response_db(result.freqs_hz, sample_rate, eq_bands)
    residual = result.left_db + eq_response - target.values_db
    
    # Compute error only within the fitted band (up to cutoff)
    fit_mask = result.freqs_hz <= cutoff_hz * 1.5  # Include some above for context
    if np.any(fit_mask):
        predicted_rms = float(np.sqrt(np.mean(residual[fit_mask] ** 2)))
        predicted_max = float(np.max(np.abs(residual[fit_mask])))
    else:
        predicted_rms = 0.0
        predicted_max = 0.0
    
    # Build report
    fit_report: dict[str, Any] = {
        'peq_bands_left': [
            {'kind': b.kind, 'freq': b.freq, 'gain_db': b.gain_db, 'q': b.q}
            for b in eq_bands
        ],
        'peq_bands_right': [
            {'kind': b.kind, 'freq': b.freq, 'gain_db': b.gain_db, 'q': b.q}
            for b in eq_bands
        ],
        'predicted_left_rms_error_db': predicted_rms,
        'predicted_right_rms_error_db': predicted_rms,
        'predicted_left_max_error_db': predicted_max,
        'predicted_right_max_error_db': predicted_max,
        'cutoff_hz': cutoff_hz,
        'max_boost_db': max_boost_db,
        'low_freq_q_cap': ROOM_LOW_FREQ_Q_CAP,
        'qualitative': 'acceptable' if (predicted_rms < 3.0) else 'marginal',
        'single_point': recording_two is None,
    }
    
    # EQ clipping assessment
    clipping = assess_eq_clipping(result.freqs_hz, sample_rate, eq_bands, eq_bands)
    fit_report['eq_clipping_assessment'] = {
        'will_clip': clipping.will_clip,
        'preamp_db': clipping.total_preamp_db,
        'headroom_loss_db': clipping.headroom_loss_db,
        'quality_concern': clipping.quality_concern,
    }
    
    # Export EQ presets
    export_equalizer_apo_parametric_txt(
        out_dir / 'equalizer_apo.txt',
        eq_bands,
        eq_bands,
        preamp_db=clipping.total_preamp_db if clipping.will_clip else None,
    )
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', eq_bands, eq_bands, samplerate=sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', eq_bands, eq_bands)
    
    # Export room FR CSV
    save_fr_csv(out_dir / 'room_fr.csv', result.freqs_hz, result.left_db, column_name='response_db')
    
    # Export target curve
    save_fr_csv(out_dir / 'target_curve.csv', target.freqs_hz, target.values_db, column_name='target_db')
    
    # Render graphs with cutoff marker
    render_fit_graphs(
        out_dir, result, target, sample_rate, eq_bands, eq_bands, cutoff_hz=cutoff_hz
    )
    
    # Trustworthiness assessment
    trust_summary = summarize_trustworthiness(result, fit_report)
    
    # Build run summary
    identity = get_app_identity()
    summary = FrontendRunSummary(
        schema_version=RUN_SUMMARY_SCHEMA_VERSION,
        kind='fit',
        out_dir=str(out_dir),
        sample_rate=sample_rate,
        frequency_points=len(result.freqs_hz),
        target=target.name,
        filters=RunFilterCounts(left=len(eq_bands), right=len(eq_bands)),
        predicted_error_db=RunErrorSummary(
            left_rms=predicted_rms,
            right_rms=predicted_rms,
            left_max=predicted_max,
            right_max=predicted_max,
        ),
        confidence=trust_summary,
        plots={
            'overview': str(out_dir / 'fit_overview.svg'),
            'left': str(out_dir / 'fit_left.svg'),
            'right': str(out_dir / 'fit_right.svg'),
        },
        results_guide=str(out_dir / 'README.txt'),
        filter_budget=FilterBudget(family='peq', max_filters=8),
        eq_clipping_assessment=fit_report['eq_clipping_assessment'],
        generated_by=identity.as_metadata(),
        cutoff_hz=cutoff_hz,
        mic_cal_applied=mic_cal is not None,
        single_point=recording_two is None,
    )
    
    # Write JSON artifacts
    save_json(out_dir / 'run_summary.json', summary.to_dict())
    save_json(out_dir / 'fit_report.json', fit_report)
    
    # Write README
    _write_room_results_guide(out_dir, eq_bands, trust_summary, fit_warnings)
    
    return RoomFitResult(
        result=result,
        eq_bands=eq_bands,
        target=target,
        fit_report=fit_report,
        run_summary=summary.to_dict(),
        out_dir=out_dir,
        warnings=fit_warnings,
    )


def prepare_room_measurement(
    spec: SweepSpec,
    mic_cal: MicCalibration | None,
    cutoff_hz: float,
    max_boost_db: float,
    listen_position_two: bool,
    out_dir: Path,
) -> dict:
    """Prepare offline measurement package for room correction.

    Generates a sweep WAV and metadata JSON for manual room measurement.
    The generated package can be played through speakers and recorded
    at the listening position(s).

    Args:
        spec: Sweep specification for the measurement signal
        mic_cal: Optional microphone calibration for field measurements
        cutoff_hz: Maximum frequency for EQ correction
        max_boost_db: Maximum allowed boost
        listen_position_two: If True, prepare for two-position measurement
        out_dir: Directory to write output files

    Returns:
        Dictionary with file paths and configuration
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from .measure import render_sweep_file, save_json
    from .app_identity import get_app_identity

    sweep_wav = out_dir / "room_sweep.wav"
    metadata_json = out_dir / "room_measurement.json"

    render_sweep_file(spec, sweep_wav)

    identity = get_app_identity()

    mic_cal_path = mic_cal.source if mic_cal else None

    metadata = {
        "generated_by": identity.as_metadata(),
        "mode": "room_offline",
        "recommended_recorder": "UMIK-1 with USB interface",
        "mic_calibration": {
            "applied": mic_cal is not None,
            "source_file": str(mic_cal_path) if mic_cal_path else None,
        },
        "measurement_config": {
            "cutoff_hz": cutoff_hz,
            "max_boost_db": max_boost_db,
            "single_point": not listen_position_two,
        },
        "sweep": {
            "sample_rate": spec.sample_rate,
            "duration_s": spec.duration_s,
            "f_start": spec.f_start,
            "f_end": spec.f_end,
            "pre_silence_s": spec.pre_silence_s,
            "post_silence_s": spec.post_silence_s,
            "amplitude": spec.amplitude,
        },
        "instructions": [
            "Connect the measurement microphone to a USB audio interface.",
            "Position the microphone at the primary listening position (ear height).",
            "Disable auto gain, limiter, low cut, and any other processing.",
            "Ensure the room is quiet during measurement.",
            *([
                "Record sweep at position 1, then move mic and repeat for position 2."
            ] if listen_position_two else [
                "Record the sweep from primary listening position only."
            ]),
        ],
        "files": {
            "sweep_wav": str(sweep_wav),
        },
    }

    save_json(metadata_json, metadata)

    return {
        "sweep_wav": sweep_wav,
        "metadata_json": metadata_json,
        "config": metadata["measurement_config"],
    }