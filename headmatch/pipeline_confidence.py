"""Confidence scoring for measurement quality assessment.

Extracted from pipeline.py (TASK-083). Contains the scoring algorithm,
threshold constants, and trustworthiness summary generation.

Scoring Model Overview
----------------------
The confidence score is an integer from 0 to 100 representing measurement quality.
Lower scores indicate more suspect measurements that may produce unreliable EQ
recommendations.

The scoring works by accumulating weighted penalties:
  1. For each quality dimension (alignment, channel match, roughness, etc.),
     we compute a normalized penalty in [0, 1] using linear interpolation
     between "warn" and "severe" thresholds.
  2. Each penalty is multiplied by a dimension-specific weight.
  3. All weighted penalties are summed; since weights sum to 100, the maximum
     total penalty is 100 points.
  4. Final score = 100 - total_penalty, clamped to [0, 100].

Penalty Calculation (_confidence_penalty):
  - value <= good_threshold: penalty = 0
  - value >= bad_threshold:  penalty = 1 (full weight applied)
  - in between:              linear interpolation

Dimension Weights and Rationale:
  - Channel mismatch (36): Highest weight because inconsistent left/right
    measurements strongly indicate seating/positioning problems that make
    EQ recommendations unreliable.
  - Roughness (28): High weight because trace roughness correlates with noise,
    movement, or seal issues during capture.
  - Residual RMS error (12): Moderate weight for post-fit prediction accuracy.
  - Alignment score (10): Timing alignment quality to reference sweep.
  - Alignment peak (8): Clarity of alignment peak vs noise/echoes.
  - Residual peak error (6): Worst-case frequency misses.

Score Labels:
  - High (>=85): Measurement looks trustworthy.
  - Medium (65-84): Usable but review before trusting fully.
  - Low (<65): Suspicious; re-run recommended.

All threshold values were empirically tuned during development based on
analysis of calibration measurements. They may be adjusted in future releases
based on user feedback and field data.
"""
from __future__ import annotations

from .analysis import MeasurementResult
from .contracts import ConfidenceSummary
from .troubleshooting import confidence_troubleshooting_steps


def _confidence_penalty(value: float, good: float, bad: float) -> float:
    """Compute normalized penalty in [0,1] via linear interpolation.

    Args:
        value: The measured value to assess.
        good: Threshold below which penalty is zero (acceptable).
        bad: Threshold above which penalty is one (severe problem).

    Returns:
        Normalized penalty in range [0.0, 1.0].
    """
    if value <= good:
        return 0.0
    if value >= bad:
        return 1.0
    return float((value - good) / max(bad - good, 1e-9))


# ── Confidence scoring thresholds ──────────────────────────────────────
# Penalty thresholds: (warning_start, severe) for _confidence_penalty.
#
# These values are empirically tuned from calibration measurements during
# development. They represent points where quality degradation becomes
# noticeable in practice.
#
# ALIGNMENT_SCORE: Measures timing alignment to reference sweep.
#   - 0.20 deviation: Audible timing drift typically becomes noticeable.
#   - 0.40 deviation: Severe misalignment likely causing EQ errors.
ALIGNMENT_SCORE_WARN = 0.20
ALIGNMENT_SCORE_SEVERE = 0.40

# ALIGNMENT_PEAK: Deficit from a perfect alignment peak ratio.
# The scorer uses 1.0 - alignment_peak_ratio, so these correspond to raw
# peak clarity ratios of 0.85 (warn) and 0.65 (severe).
#   - 0.15 deficit: Some noise/echoes present but usually manageable.
#   - 0.35 deficit: Confusing echoes or noise dominate; timing unreliable.
ALIGNMENT_PEAK_WARN = 0.15
ALIGNMENT_PEAK_SEVERE = 0.35

# CHANNEL_MISMATCH: RMS difference between left and right channels in dB.
#   - 0.8 dB: Slight asymmetry, often acceptable.
#   - 2.5 dB: Significant mismatch suggesting seating inconsistency.
CHANNEL_MISMATCH_WARN_DB = 0.8
CHANNEL_MISMATCH_SEVERE_DB = 2.5

# ROUGHNESS: Average absolute deviation from smoothed trace in dB.
#   - 0.3 dB: Minor roughness from slight noise or movement.
#   - 1.5 dB: Very rough trace indicating capture problems.
ROUGHNESS_WARN_DB = 0.3
ROUGHNESS_SEVERE_DB = 1.5

# RESIDUAL_RMS: Predicted post-EQ RMS error in dB.
#   - 2.0 dB: Moderate residual error, EQ should help.
#   - 4.5 dB: Large residual suggesting poor fit or bad measurement.
RESIDUAL_RMS_WARN_DB = 2.0
RESIDUAL_RMS_SEVERE_DB = 4.5

# RESIDUAL_PEAK: Predicted worst-case post-EQ error in dB.
#   - 4.0 dB: Some frequencies will still deviate noticeably.
#   - 9.0 dB: Severe misses indicating unreliable EQ.
RESIDUAL_PEAK_WARN_DB = 4.0
RESIDUAL_PEAK_SEVERE_DB = 9.0

# Penalty weights: Each dimension's contribution to total penalty.
# Weights are chosen to reflect relative importance to EQ reliability.
# Channel mismatch and roughness are weighted highest because they correlate
# most strongly with unreliable EQ recommendations.
# Sum of all weights = 100, ensuring max penalty is 100 points.
ALIGNMENT_WEIGHT = 10          # Timing alignment to reference
ALIGNMENT_PEAK_WEIGHT = 8      # Clarity of alignment peak
CHANNEL_MISMATCH_WEIGHT = 36   # Left/right consistency (highest priority)
ROUGHNESS_WEIGHT = 28          # Trace smoothness (high priority)
RESIDUAL_RMS_WEIGHT = 12       # Predicted average post-EQ error
RESIDUAL_PEAK_WEIGHT = 6       # Predicted worst-case post-EQ error

# Warning thresholds: User-facing advisory message triggers.
# These are distinct from scoring thresholds - they control when we
# generate specific warning messages for the user, not the score itself.
# Values are intentionally stricter than penalty thresholds to provide
# early warning before quality degrades significantly.
ALIGNMENT_SCORE_WARNING_THRESHOLD = 0.80   # Warn if alignment weaker than this
ALIGNMENT_PEAK_WARNING_THRESHOLD = 0.85    # Warn if peak clarity below this

# Score label boundaries: Define high/medium/low categories shown to users.
# SCORE_HIGH_THRESHOLD (85): Minimum for "high confidence" - measurement
#   is trustworthy for normal use.
# SCORE_MEDIUM_THRESHOLD (65): Minimum for "medium confidence" - usable but
#   review recommended. Below this is "low confidence" - re-run advised.
SCORE_HIGH_THRESHOLD = 85
SCORE_MEDIUM_THRESHOLD = 65


def summarize_trustworthiness(result: MeasurementResult, report: dict) -> ConfidenceSummary:
    """Score measurement quality and produce a user-facing confidence summary.

    Computes a 0-100 confidence score by accumulating weighted penalties across
    six quality dimensions: alignment accuracy, alignment peak clarity,
    channel mismatch, trace roughness, predicted residual RMS error, and
    predicted residual peak error.

    The algorithm:
      1. Extract diagnostic metrics from the measurement result.
      2. Compute normalized penalty [0,1] for each dimension using linear
         interpolation between warn/severe thresholds.
      3. Multiply each penalty by its dimension weight and sum.
      4. Score = 100 - total_penalty, clamped to [0, 100].
      5. Assign label (high/medium/low) based on score thresholds.
      6. Generate user-facing headline, interpretation, reasons list,
         warnings, and detailed metrics.

    Args:
        result: MeasurementResult containing diagnostic metrics.
        report: Dict with predicted error fields:
            - predicted_left_rms_error_db: float
            - predicted_right_rms_error_db: float
            - predicted_left_max_error_db: float
            - predicted_right_max_error_db: float

    Returns:
        ConfidenceSummary with fields:
            - score: int (0-100)
            - label: 'high' | 'medium' | 'low'
            - headline: Short user-facing status message
            - interpretation: Longer explanation of what the score means
            - reasons: Tuple of metric descriptions for transparency
            - warnings: Tuple of specific advisory messages
            - metrics: Dict of raw diagnostic values
    """
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
        label=label,  # type: ignore[arg-type]
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
