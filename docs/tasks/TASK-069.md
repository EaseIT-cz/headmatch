# TASK-069 — Fix alignment_peak_ratio for negative offsets

## Summary
In `_align_recording_to_reference`, when the best alignment offset is negative, `peak_index` goes negative, the bounds check silently returns `peak = 0.0`, and `alignment_peak_ratio` is incorrectly degraded. This penalises confidence for recordings that start early relative to the reference.

## Scope
- Fix the `peak_index` computation to handle negative offsets correctly.
- Add a test with a recording that has a negative alignment offset, asserting `alignment_peak_ratio > 0`.

## Suggested files
- `headmatch/analysis.py`
- `tests/test_pipeline.py`
