# TASK-110 - Standardize error hierarchy

## Summary
Define a coherent exception hierarchy with `HeadMatchError` as the base class, replacing inconsistent use of `ValueError`, `RuntimeError`, and `ConnectionError`.

## Context
The codebase currently raises `ValueError` in some places, `RuntimeError` in others, and `ConnectionError` for network issues. There is no clear pattern for user-facing vs internal errors. This forces callers to use broad `except` clauses and reduces clarity.

The code review identified this as a medium-priority consistency improvement.

## Scope
- Define `HeadMatchError` base exception class
- Define subclasses:
  - `MeasurementError` — measurement pipeline failures
  - `ConfigError` — configuration loading/saving failures
  - `NetworkError` — HTTP/network failures
  - `AudioBackendError` — audio device/pipe failures (optional)
- Audit existing exception raises and convert to appropriate subclass
- Update callers to catch at appropriate granularity
- Update tests to verify exception types

## Out of scope
- Changing error messages (keep existing text)
- Adding new error conditions beyond hierarchy
- Frontend-specific error handling logic

## Acceptance criteria
- All `raises` docstrings updated to reference new exception types
- Backward compatibility: existing `except ValueError` clauses still work where appropriate
- Consistent exception types per error category
- Tests verify correct exception types

## Suggested files/components
- `headmatch/exceptions.py` (new)
- `headmatch/pipeline.py`
- `headmatch/audio_backend.py`
- `headmatch/headphone_db.py`
- All modules that currently raise generic exceptions
