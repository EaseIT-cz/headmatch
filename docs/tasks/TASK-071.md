# TASK-071 — Remove dead code: validate_stereo_audio and inverse_sweep

## Summary
Two functions are defined but never called anywhere in the codebase:
- `validate_stereo_audio` in `io_utils.py` — superseded by `_coerce_measurement_audio` in `analysis.py`
- `inverse_sweep` in `signals.py` — orphaned; the analysis pipeline uses plain FFT ratio instead

## Scope
- Remove both functions.
- If `inverse_sweep` is intentionally kept for future Farina deconvolution work, move it behind a comment or into a `_future/` module. Otherwise delete it.
- Remove any related dead imports.

## Suggested files
- `headmatch/io_utils.py`
- `headmatch/signals.py`
