# TASK-005 — Strengthen target-curve loading and clone workflow

## Summary
Make target curve loading and cloning safer across common CSV formats.

## Context
Audiophile users will often start from published measurement CSVs. The software should accept common layouts without requiring data-cleaning skills.

## Scope
- Review CSV loader heuristics.
- Add support for more common frequency/response column naming patterns.
- Improve clone-target documentation and examples.
- Validate normalization behavior.

## Out of scope
- Building a measurement database.
- New file formats.

## Acceptance criteria
- Common target CSV layouts load reliably.
- Clone targets remain normalized and usable by the fit pipeline.
- Documentation explains the supported CSV shapes in plain language.

## Suggested files/components
- `headmatch/io_utils.py`
- `headmatch/targets.py`
- `README.md`
- `tests/`
