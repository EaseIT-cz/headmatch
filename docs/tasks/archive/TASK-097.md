# TASK-097: Fix docstring drift in measure.py and audio_backend.py

## Summary
Fix docstring drift in `headmatch/measure.py` and `headmatch/audio_backend.py`.

## Context
Docstrings in source files may not accurately reflect current behavior or arguments. This creates confusion for users reading `headmeasure --help` or `headmatch measure --help`.

## Scope
- Review `headmatch/measure.py` docstring for accuracy
- Review `headmatch/audio_backend.py` docstring for accuracy
- Update any outdated text
- Verify CLI help output matches updated docstrings

## Out-of-scope
- Rewriting docstrings from scratch
- Adding new docstrings for undocumented features (create separate tasks)

## Acceptance criteria
- All public functions in `measure.py` and `audio_backend.py` have accurate, up-to-date docstrings
- CLI help (`headmeasure --help`, `headmatch measure --help`) displays correct information
- No discrepancies between docstring and implementation

## Suggested files/components
- `headmatch/measure.py`
- `headmatch/audio_backend.py`
