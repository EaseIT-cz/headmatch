# TASK-072 — Add smoke tests for plots.py and unit tests for signals.py

## Summary
Two modules have zero direct test coverage:
- `plots.py` (188 lines) — SVG graph renderer, never tested
- `signals.py` (89 lines) — sweep generation, smoothing, grid helpers — only exercised indirectly through integration tests

## Scope
- Add smoke tests for `render_fit_graphs`: verify it produces non-empty SVG output without exceptions for typical inputs.
- Add unit tests for `generate_log_sweep` (correct length, frequency range), `fractional_octave_smoothing` (flat input stays flat, known peak is smoothed), and `geometric_log_grid` (correct point count, monotonic, covers range).

## Suggested files
- `tests/test_plots.py` (new)
- `tests/test_signals.py` (new)
