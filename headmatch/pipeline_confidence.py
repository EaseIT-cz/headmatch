"""Confidence scoring for measurement quality assessment.

Extracted from pipeline.py (TASK-083). Contains the scoring algorithm,
threshold constants, and trustworthiness summary generation.
"""
from __future__ import annotations

from .analysis import MeasurementResult
from .contracts import ConfidenceSummary
from .troubleshooting import confidence_troubleshooting_steps


def _confidence_penalty(value: float, good: float, bad: float) -> float:
    if value <= good:
        return 0.0
    if value >= bad:
        return 1.0
    return float((value - good) / max(bad - good, 1e-9))


# ── Confidence scoring thresholds ──────────────────────────────────────
# Penalty thresholds: (warning_start, severe) for _confidence_penalty
ALIGNMENT_SCORE_WARN = 0.20
ALIGNMENT_SCORE_SEVERE = 0.40
ALIGNMENT_PEAK_WARN = 0.15
ALIGNMENT_PEAK_SEVERE = 0.35
CHANNEL_MISMATCH_WARN_DB = 0.8
CHANNEL_MISMATCH_SEVERE_DB = 2.5
ROUGHNESS_WARN_DB = 0.3
ROUGHNESS_SEVERE_DB = 1.5
RESIDUAL_RMS_WARN_DB = 2.0
RESIDUAL_RMS_SEVERE_DB = 4.5
RESIDUAL_PEAK_WARN_DB = 4.0
RESIDUAL_PEAK_SEVERE_DB = 9.0

# Penalty weights (sum to 100)
ALIGNMENT_WEIGHT = 10
ALIGNMENT_PEAK_WEIGHT = 8
CHANNEL_MISMATCH_WEIGHT = 36
ROUGHNESS_WEIGHT = 28
RESIDUAL_RMS_WEIGHT = 12
RESIDUAL_PEAK_WEIGHT = 6

# Warning thresholds (for user-facing messages)
ALIGNMENT_SCORE_WARNING_THRESHOLD = 0.80
ALIGNMENT_PEAK_WARNING_THRESHOLD = 0.85

# Score label boundaries
SCORE_HIGH_THRESHOLD = 85
SCORE_MEDIUM_THRESHOLD = 65


def summarize_trustworthiness(result: MeasurementResult, report: dict) -> ConfidenceSummary:
    """Score measurement quality and produce a user-facing confidence summary."""
    diagnostics = result.diagnostics
    roughness = max(diagnostics['left_roughness_db'], diagnostics['right_roughness_db'])
    predicted_rms = max(report['predicted_left_rms_error_db'], report['predicted_right_rms_error_db'])
    predicted_max = max(report['predicted_left_max_error_db'], report['predicted_right_max_error_db'])

    penalties = {
        'alignment': _confidence_penalty(1.0 - diagnostics['alignment_reference_score'], ALIGNMENT_SCORE_WARN, ALIGNMENT_SCORE_SEVERE),
        'alignment_peak': _confidence_penalty(1.0 - diagnostics['alignment_peak_ratio'], ALIGNMENT_PEAK_WARN, ALIGNMENT_PEAK_SEVERE),
        'channel_mismatch': _confidence_penalty(diagnostics['channel_mismatch_rms_db'], CHANNEL_MISMATCH_WARN_DB, CHANNEL_MISMATCH_SEVERE_DB),
        'roughness': _confidence_penalty(roughness, ROUGHNESS_WARN_DB, ROUGHNESS_SEVERE_DB),
        'residual_rms': _confidence_penalty(predicted_rms, RESIDUAL_RMS_WARN_DB, RESIDUAL_RMS_SEVERE_DB),
        'residual_peak': _confidence_penalty(predicted_max, RESIDUAL_PEAK_WARN_DB, RESIDUAL_PEAK_SEVERE_DB),
    }
    penalty_points = (
        penalties['alignment'] * ALIGNMENT_WEIGHT
        + penalties['alignment_peak'] * ALIGNMENT_PEAK_WEIGHT
        + penalties['channel_mismatch'] * CHANNEL_MISMATCH_WEIGHT
        + penalties['roughness'] * ROUGHNESS_WEIGHT
        + penalties['residual_rms'] * RESIDUAL_RMS_WEIGHT
        + penalties['residual_peak'] * RESIDUAL_PEAK_WEIGHT
    )
    score = max(0, min(100, int(round(100 - penalty_points))))

    warnings: list[str] = []
    if diagnostics['alignment_reference_score'] < ALIGNMENT_SCORE_WARNING_THRESHOLD:
        warnings.append('Alignment to the sweep was weaker than expected, so the measurement timing may be unreliable.')
    if diagnostics['alignment_peak_ratio'] < ALIGNMENT_PEAK_WARNING_THRESHOLD:
        warnings.append('The sweep alignment peak was not clearly dominant, which can happen with extra noise or confusing echoes.')
    if diagnostics['channel_mismatch_rms_db'] >= CHANNEL_MISMATCH_WARN_DB:
        warnings.append('Left and right measurements differ more than usual, which often means the headset or microphones were not seated consistently.')
    if roughness >= ROUGHNESS_WARN_DB:
        warnings.append('The raw trace is rougher than expected, suggesting noise, movement, or a leaky seal during capture.')
    if predicted_rms >= RESIDUAL_RMS_WARN_DB:
        warnings.append('The fitted result still leaves noticeable residual error, so the generated EQ should be treated as provisional.')
    if predicted_max >= RESIDUAL_PEAK_WARN_DB:
        warnings.append('Some frequencies still miss the target by a wide margin, so inspect the graphs before trusting the preset.')

    if score >= SCORE_HIGH_THRESHOLD:
        label = 'high'
        headline = 'This run looks trustworthy.'
        interpretation = 'The measurement aligned cleanly, the channels agree reasonably well, and the predicted post-EQ error is low enough for normal use.'
    elif score >= SCORE_MEDIUM_THRESHOLD:
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

    return ConfidenceSummary(
        score=score,
        label=label,
        headline=headline,
        interpretation=interpretation,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        metrics={
            'alignment_reference_score': diagnostics['alignment_reference_score'],
            'alignment_peak_ratio': diagnostics['alignment_peak_ratio'],
            'channel_mismatch_rms_db': diagnostics['channel_mismatch_rms_db'],
            'left_roughness_db': diagnostics['left_roughness_db'],
            'right_roughness_db': diagnostics['right_roughness_db'],
            'capture_rms_dbfs': diagnostics['capture_rms_dbfs'],
            'predicted_rms_error_db': predicted_rms,
            'predicted_max_error_db': predicted_max,
        },
    )
