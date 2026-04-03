# TASK-055 — Add exact-count PEQ fitting mode

## Summary
Add an exact-count PEQ mode so HeadMatch can emit exactly N parametric bands for device-constrained workflows instead of only conservative up-to-N fits.

## Context
Current `max_filters` behavior is conservative: the fitter may stop early and emit fewer than N bands. That is reasonable for a safety-first default, but it does not match device-constrained workflows where a user must populate exactly 10, 20, or similar parametric slots.

The design should not become a one-way door. Exact-count PEQ should be introduced as a fill-policy choice that can later coexist with a GraphicEQ / fixed-band mode on top of the same residual/objective layer.

## Scope
- Introduce an exact-count PEQ fitting mode.
- Preserve current conservative up-to-N behavior as the default.
- Make the budget/fill policy explicit in the backend API.
- Ensure exports and summaries reflect the actual band count used.
- Update tests to cover both up-to-N and exact-N behavior.

## Out of scope
- GraphicEQ implementation.
- Broad GUI redesign.
- New measurement math outside what is needed for the fit-mode addition.

## Acceptance criteria
- The backend supports a mode that emits exactly N PEQ bands when requested.
- Existing conservative behavior remains available and unchanged by default.
- The implementation is structured so a future GraphicEQ mode can reuse the same objective/residual layer.
- Full test suite passes.

## Suggested files/components
- `headmatch/peq.py`
- `headmatch/pipeline.py`
- `headmatch/cli.py` if mode selection is exposed there
- `headmatch/gui.py` only if mode selection is exposed there
- `tests/test_peq_exporters.py`
- `tests/test_pipeline.py`
