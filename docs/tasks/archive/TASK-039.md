# TASK-039 — Validate saved PipeWire targets in `headmatch doctor`

## Summary
Make `headmatch doctor` more useful by checking whether saved PipeWire playback/capture target names still match current discovery results.

## Context
The first diagnostics slice now reports whether saved targets are configured, but it does not verify whether those saved names still correspond to real PipeWire nodes. That leaves an obvious gap in the setup-readiness story.

## Scope
- Extend `headmatch doctor` so it compares saved PipeWire targets against current discovery results when discovery is available.
- Report clear status for configured-and-found vs configured-but-missing targets.
- Keep the implementation conservative and beginner-friendly.
- Update tests as needed.

## Out of scope
- New PipeWire discovery ranking or heuristics.
- Major diagnostics redesign.
- GUI diagnostics workflow.
- Non-PipeWire device layers.

## Acceptance criteria
- `headmatch doctor` can tell users whether saved playback/capture targets still exist.
- Missing saved targets are reported clearly and actionably.
- Existing diagnostics behavior remains stable otherwise.
- Full test suite passes.

## Suggested files/components
- `headmatch/cli.py`
- `headmatch/measure.py`
- `tests/test_cli.py`
- `tests/test_measure.py` if needed
