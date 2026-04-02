# TASK-051 — Audit measurement, normalization, and PEQ math for edge-case bugs

## Summary
Audit the non-clone parts of the backend math path — sweep/measurement transforms, normalization, and PEQ fitting heuristics — and fix any confirmed bugs or edge-case failures.

## Context
The user wants to exclude backend math from the equation while debugging real-world results. Clone-target semantics look suspicious already, but the rest of the math path should be audited too so obvious edge-case bugs and incorrect assumptions are removed.

## Scope
- Audit `signals.py`, `analysis.py`, and `peq.py` math/logic for confirmed issues.
- Fix small but real bugs or edge-case failures if found.
- Add tests for the corrected behavior.
- Keep changes conservative and evidence-based.

## Out of scope
- Broad DSP redesign.
- Replacing the current measurement model with a new algorithm.
- GUI/CLI/TUI product work.

## Acceptance criteria
- Confirmed backend math issues are fixed.
- Edge-case behavior is covered by tests.
- No speculative churn or large redesign lands without justification.
- Full test suite passes.

## Suggested files/components
- `headmatch/signals.py`
- `headmatch/analysis.py`
- `headmatch/peq.py`
- `tests/test_pipeline.py`
- `tests/test_peq_exporters.py`
- new focused tests if needed
