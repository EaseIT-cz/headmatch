# TASK-064 — Add RBJ reference coefficient tests for biquad_response_db

## Summary
Add tests that verify `biquad_response_db` coefficients match the RBJ Audio EQ Cookbook formulas across a dense parameter grid for all three filter types (peaking, lowshelf, highshelf).

## Context
`peq.py` implements biquad coefficient computation inline in `biquad_response_db`. The formulas follow the RBJ cookbook pattern but have never been tested against known reference values. Two independent external reviews flagged this as a gap.

The current implementation:
- Peaking: uses `A = 10^(gain/40)`, `alpha = sin(w0)/(2*Q)` — standard RBJ.
- Lowshelf/highshelf: uses a shelf slope parameter `S` clamped to [0.1, 1.0] and recomputes alpha — RBJ variant.

## Scope
- Generate reference coefficient values from the RBJ formulas for a grid of parameters:
  - Fc: [30, 100, 1000, 5000, 15000] Hz
  - Q: [0.3, 0.707, 2.0, 8.0]
  - Gain: [-12, -3, 0, +3, +12] dB
  - Fs: [44100, 48000, 96000]
- For each combination and filter type, assert that the computed b/a coefficients match within float64 tolerance.
- Test edge cases: gain=0 (should produce unity), Q near minimum, Fc near Nyquist.

## Out of scope
- Changing the coefficient computation.
- Adding new filter types.
- Performance optimization.

## Acceptance criteria
- At least 60 reference coefficient test points across the parameter grid.
- Zero-gain filters produce a flat (0 dB) response.
- All tests pass. Existing test suite unaffected.

## Suggested files/components
- `tests/test_peq_exporters.py` (or a new `tests/test_biquad_coefficients.py`)
- `headmatch/peq.py` (read-only — no changes expected)
