# TASK-060 — Refactor TASK-054 tests to use pytest.raises

## Summary
The mono and duplicated-channel rejection tests added in TASK-054 use manual `try/except/assert False` instead of `pytest.raises(ValueError, match=...)`. This produces worse failure messages and is non-idiomatic.

## Context
Two tests in `test_pipeline.py`:
- `test_analyze_rejects_mono_recording`
- `test_analyze_rejects_duplicated_channel_capture`

Both use a pattern that should be replaced with `pytest.raises`.

## Scope
- Rewrite both tests to use `pytest.raises(ValueError, match=...)`.

## Out of scope
- Changing test logic or coverage.
- Touching other tests.

## Acceptance criteria
- Both tests use `pytest.raises`.
- Match strings verify the error message content.
- Full test suite passes.

## Suggested files/components
- `tests/test_pipeline.py`
