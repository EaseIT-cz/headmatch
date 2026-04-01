# TASK-021 — Improve PipeWire coordination and offline import tolerance

## Summary
Harden live capture and recorder-first import so measurement runs fail less often in real-world use.

## Context
The next product risk is not workflow shape anymore. It is capture reliability. PipeWire device matching and real recorder WAV imports are the most likely places for non-technical users to get stuck.

## Scope
- Improve PipeWire node selection / matching behavior.
- Make live playback/record coordination more predictable.
- Accept a wider range of recorder-generated WAV files where safe.
- Improve user-facing validation/error messages where necessary.

## Out of scope
- Full device auto-discovery redesign.
- Cross-platform audio backends.
- GUI/TUI redesign.

## Acceptance criteria
- Live capture handling is more robust than the current baseline.
- Offline recorder imports accept more realistic files without manual cleanup.
- Failures remain actionable and beginner-readable.
- Tests cover at least the main new cases.

## Suggested files/components
- `headmatch/measure.py`
- `headmatch/analysis.py`
- `headmatch/cli.py`
- `tests/`
