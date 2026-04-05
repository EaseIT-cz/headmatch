# TASK-082 — Replace Python-loop peak detection in alignment with scipy.signal.find_peaks

## Summary
The alignment function `_align_recording_to_reference()` uses a Python for-loop to scan the entire cross-correlation array for local maxima. Replace it with `scipy.signal.find_peaks` for better performance on long recordings.

## Context
On long recordings the Python loop becomes a noticeable cost. `scipy.signal.find_peaks` does the same neighbor-comparison logic in C and supports height/threshold filtering natively. SciPy is already a dependency.

## Scope
- Replace the manual local-maxima loop in `headmatch/analysis.py` (lines ~64–67) with `scipy.signal.find_peaks(corr_abs, height=corr_threshold)`
- Preserve existing fallback behavior: if no peaks found, fall back to argmax
- Add a unit test with a synthetic echo-heavy signal to verify alignment stability after the change

## Out of scope
- Changing alignment logic or correlation method
- Changing the public API of any analysis function
- Performance benchmarking beyond correctness

## Acceptance criteria
- `_align_recording_to_reference` produces the same alignment offsets on existing test data
- New test: synthetic recording with known delay + echo returns correct offset
- All existing tests pass
- No new dependencies

## Suggested files
- `headmatch/analysis.py` (alignment function)
- `tests/test_analysis.py` (new alignment robustness test)
