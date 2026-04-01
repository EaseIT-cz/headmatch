# TASK-023 — Refine PEQ fitting and CamillaDSP export polish

## Summary
Make the generated EQ safer and the exported CamillaDSP outputs more practical for real setups.

## Context
The software already produces usable EQ, but the remaining polish should bias toward broad, conservative correction and cleaner export outputs.

## Scope
- Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
- Improve CamillaDSP export templates for practical use.
- Keep generated outputs understandable for non-technical users.

## Out of scope
- New DSP backends.
- Major fitter redesign.
- New GUI/TUI workflows.

## Acceptance criteria
- Generated EQ is at least as safe as before, with better practical defaults.
- CamillaDSP outputs are more usable out of the box.
- Tests or fixture-based checks cover the changed behavior.

## Suggested files/components
- `headmatch/peq.py`
- `headmatch/exporters.py`
- `headmatch/pipeline.py`
- `tests/`
