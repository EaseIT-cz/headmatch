# TASK-065 — Verify biquad numerical stability for extreme filter parameters

## Summary
Test that `biquad_response_db` remains numerically stable and produces finite, bounded results for extreme parameter combinations that stress float64 precision.

## Context
Biquad filters are known to lose numerical stability when:
- Fc is very low relative to Fs (poles near z=1)
- Fc is very close to Nyquist (poles near z=-1)
- Q is very high (narrow bandwidth, poles near unit circle)
- Gain is very large

The current implementation uses `scipy.signal.freqz` which evaluates the transfer function on the unit circle — this is numerically more stable than direct DF2 filtering but coefficient computation itself can overflow or lose precision.

## Scope
- Test parameter combinations:
  - Fc=10 Hz at Fs=96000 (very low relative frequency)
  - Fc=23000 Hz at Fs=48000 (near Nyquist)
  - Q=50.0 (extremely narrow)
  - Gain=±24 dB (large boost/cut)
  - Combined: low Fc + high Q, high Fc + high Q
- Assert: all output values are finite (no NaN/Inf), response is bounded within [-100, +100] dB, and peak gain is within 3 dB of the requested gain at the center frequency.

## Out of scope
- Switching to double-precision or DF2T runtime form (this task is diagnosis only).
- Changing the coefficient formulas.

## Acceptance criteria
- All extreme parameter combinations produce finite, bounded output.
- Any discovered instabilities are documented as comments in the test file.
- Full test suite passes.

## Suggested files/components
- `tests/test_peq_exporters.py` (or `tests/test_biquad_coefficients.py`)
- `headmatch/peq.py` (read-only unless a fix is needed)
