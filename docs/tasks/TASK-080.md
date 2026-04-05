# TASK-080 — Replace O(N²) fractional-octave smoothing with O(N) implementation

## Summary
Replace the NxN Gaussian weight matrix in `fractional_octave_smoothing()` with a log-domain resample + 1D Gaussian filter approach. Same behavior within tolerance, O(N) time and memory.

## Context
The current implementation builds a full NxN outer-product matrix of log-frequency differences. At the default grid (~480 points) this is fine, but dense imported curves (thousands+ points) will blow up memory and stall. Multiple independent code reviews flagged this as the highest-ROI performance fix.

SciPy is already a dependency, so `scipy.ndimage.gaussian_filter1d` is available at no extra cost.

## Scope
- Replace the matrix-based smoothing in `headmatch/signals.py` (`fractional_octave_smoothing`) with:
  1. Interpolate onto a uniform log2-frequency grid
  2. Apply `gaussian_filter1d` with sigma derived from the octave fraction
  3. Interpolate back to the original frequency points
- Add a regression test: compare old vs new output on the default ~480-point grid, assert max absolute difference < 0.1 dB
- Add a scalability test: run smoothing on 10k+ points, assert it completes in < 2 seconds and doesn't allocate an NxN array

## Out of scope
- Changing the smoothing fraction default or any caller behavior
- Modifying any other module's smoothing calls
- Changing the public API signature

## Acceptance criteria
- `fractional_octave_smoothing` produces results within 0.1 dB of the old implementation on the default grid
- 10k-point input completes in < 2s (no quadratic blowup)
- All existing tests pass
- No new dependencies added

## Suggested files
- `headmatch/signals.py` (lines 58–68)
- `tests/test_signals.py` (new regression + perf tests)
