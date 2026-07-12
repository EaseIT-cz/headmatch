# Confidence Scoring

This document describes the measurement quality confidence scoring system used by headmatch.

## Overview

The confidence score is a number from 0 to 100 that represents how trustworthy a measurement is. Lower scores indicate measurements that may produce unreliable EQ recommendations.

The score is computed from six quality dimensions, each measuring a different aspect of the measurement:

1. **Alignment quality** — How well the captured audio aligns with the reference sweep
2. **Alignment peak clarity** — How clearly the alignment peak stands out from noise/echoes
3. **Channel mismatch** — How different the left and right channel measurements are
4. **Trace roughness** — How noisy/jagged the raw measurement traces are
5. **Predicted residual RMS error** — Estimated average error after EQ
6. **Predicted residual peak error** — Worst-case frequency error after EQ

## Scoring Algorithm

The algorithm works by accumulating weighted penalties:

1. For each dimension, compute a normalized penalty in [0, 1] using linear interpolation between empirical "warn" and "severe" thresholds.
2. Multiply each penalty by its dimension-specific weight.
3. Sum all weighted penalties (weights total 100, so max penalty is 100 points).
4. Score = 100 - total_penalty, clamped to [0, 100].

Penalty calculation:
- Below "warn" threshold: 0 penalty (good)
- Above "severe" threshold: full weight penalty (bad)
- Between thresholds: linearly interpolated penalty

## Penalty Dimensions

| Dimension | Weight | Description | Warn Threshold | Severe Threshold |
|-----------|--------|-------------|----------------|------------------|
| Channel mismatch | 36 | L/R consistency in dB | 0.8 dB | 2.5 dB |
| Trace roughness | 28 | Deviation from smooth curve in dB | 0.3 dB | 1.5 dB |
| Residual RMS error | 12 | Predicted post-EQ average error in dB | 2.0 dB | 4.5 dB |
| Alignment quality | 10 | Reference alignment score (inverted) | 0.20 | 0.40 |
| Alignment peak clarity | 8 | Peak clarity deficit (`1 - alignment_peak_ratio`) | 0.15 deficit (raw ratio 0.85) | 0.35 deficit (raw ratio 0.65) |
| Residual peak error | 6 | Predicted worst-case frequency error in dB | 4.0 dB | 9.0 dB |

### Threshold Rationale

**Alignment score** (0.20 warn, 0.40 severe):
Measures timing alignment deviation from the reference sweep. A deviation of 0.20 is when audible timing drift typically becomes noticeable, while 0.40 represents severe misalignment likely to cause EQ errors.

**Alignment peak clarity** (0.15 warn deficit, 0.35 severe deficit):
The scorer uses `1 - alignment_peak_ratio`, so the penalty starts when the raw peak clarity ratio drops below 0.85 and is severe at 0.65 or lower.

**Channel mismatch** (0.8 dB warn, 2.5 dB severe):
Left/right RMS difference in dB. 0.8 dB represents slight asymmetry that may be acceptable; 2.5 dB suggests significant mismatch likely due to inconsistent seating.

**Trace roughness** (0.3 dB warn, 1.5 dB severe):
Average deviation from a smoothed trace in dB. 0.3 dB indicates minor roughness from slight noise; 1.5 dB indicates severe roughness suggesting movement or seal issues during capture.

**Residual RMS error** (2.0 dB warn, 4.5 dB severe):
Predicted average error after applying EQ in dB. 2.0 dB is moderate residual error where EQ should still help; 4.5 dB suggests a poor fit or bad measurement.

**Residual peak error** (4.0 dB warn, 9.0 dB severe):
Predicted worst-case frequency miss after EQ in dB. 4.0 dB means some frequencies will deviate noticeably; 9.0 dB indicates severe misses making EQ unreliable.

## Score Interpretation

The final score maps to three user-facing labels:

| Label | Score Range | Interpretation |
|-------|-------------|----------------|
| High | 85–100 | Measurement looks trustworthy for normal use. |
| Medium | 65–84 | Usable but review before trusting fully. There may be minor stability concerns. |
| Low | 0–64 | Suspicious; re-run recommended. One or more signals suggest measurement or fit may not be reliable. |

## Implementation Notes

- All threshold values were empirically tuned during development based on calibration measurements and may be adjusted in future releases based on user feedback and field data.
- The weights reflect relative priority: channel mismatch and roughness are highest because they correlate most strongly with unreliable EQ recommendations.
- Warning messages are generated separately from scoring and use slightly stricter thresholds to provide early warning.
