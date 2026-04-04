# TASK-068 — Fix dead mask in _metrics (pipeline.py)

## Summary
`_metrics` uses `mask = (np.arange(len(err)) >= 0)` which is always True. The RMS error calculation includes sub-20 Hz and above-18 kHz noise, inflating confidence penalties.

## Scope
- Replace the dead mask with a proper band-limited mask (e.g., 80–12000 Hz), consistent with the `_band_mask` used for roughness/mismatch in `analysis.py`.
- Accept `freqs_hz` as a parameter so the mask can be frequency-aware.

## Acceptance criteria
- RMS error is calculated only within the audible band.
- Existing confidence tests are updated to reflect the corrected metric.
- Full test suite passes.

## Suggested files
- `headmatch/pipeline.py`
- `tests/test_pipeline.py`
