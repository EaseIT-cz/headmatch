# TASK-031 — Add typed confidence and run-summary contracts

## Summary
Replace the most important ad-hoc confidence/run-summary dictionaries with lightweight typed contracts so GUI/CLI confidence-presentation work can evolve safely.

## Context
HeadMatch now treats confidence/trust output as product behavior, not just backend diagnostics. The current payloads are still mostly passed around as untyped dicts in `pipeline.py`, reports, and frontend-facing summary handling. That is increasingly risky as GUI/CLI polish continues.

## Scope
- Introduce lightweight typed structures for the confidence summary and the frontend-facing run summary payload.
- Reduce ad-hoc dict construction/access where it improves clarity and safety.
- Preserve JSON output shape unless a small compatibility-safe cleanup is explicitly justified.
- Update tests as needed.

## Out of scope
- New confidence heuristics.
- GUI redesign.
- CLI messaging redesign.
- Large schema/version changes.

## Acceptance criteria
- Confidence/run-summary creation is backed by clearer typed structures instead of only free-form dicts.
- Existing JSON outputs remain compatible with current tests and frontend readers.
- The refactor makes future GUI/CLI confidence-presentation work safer and easier to review.
- Full test suite passes.

## Suggested files/components
- `headmatch/contracts.py`
- `headmatch/pipeline.py`
- `headmatch/history.py` if needed
- `tests/test_pipeline.py`
- `tests/test_history.py`
