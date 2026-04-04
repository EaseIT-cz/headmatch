# TASK-075 — Parameterise _band_mask frequency limits

## Summary
`_band_mask` in `analysis.py` hardcodes 80–8000 Hz for roughness and mismatch diagnostics. These should be parameters so they can be adjusted for different use cases (sub-bass analysis, extended HF evaluation) or referenced from a single source of truth.

## Scope
- Make `_band_mask` accept `low_hz` and `high_hz` as parameters with defaults matching the current values.
- Update call sites to use the parameterised version.
- No functional change for default behaviour.

## Acceptance criteria
- `_band_mask` accepts optional frequency bounds.
- Default behaviour is unchanged.
- Full test suite passes.

## Suggested files
- `headmatch/analysis.py`
