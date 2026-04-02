# TASK-058 — Expand synthetic regression coverage for fitting/export edge cases

## Summary
Strengthen the synthetic regression suite around fitting and export behavior so backend bugs can be caught reliably without depending on unavailable real hardware fixtures.

## Context
Real-world hardware fixtures are not practical right now because there is no stable shared measurement setup available in-repo. Synthetic coverage is still the right backbone, but it should be expanded to better cover the kinds of failures we have recently found:
- clone-target semantics
- PEQ underfitting
- filter-budget handling
- exact-count behavior
- export ordering and formatting

## Scope
- Add focused synthetic regression tests for fitting/export edge cases.
- Prefer deterministic, small fixtures over broad slow tests.
- Cover the failure modes we have already fixed and the ones introduced by new fit modes.
- Keep this as a test/validation task, not a product redesign.

## Out of scope
- Real hardware capture fixtures.
- GUI work.
- Broad backend redesign without a concrete failing case.

## Acceptance criteria
- Synthetic tests cover the known edge cases more explicitly.
- New fit/export features can be validated without needing physical hardware.
- Full test suite passes.

## Suggested files/components
- `tests/test_peq_exporters.py`
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py`
- new focused synthetic tests if useful
