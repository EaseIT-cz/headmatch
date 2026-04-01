# TASK-027 — Update docs and output guides for APO export

## Summary
Document APO export clearly in README, architecture/backlog, and generated output guides.

## Context
Once APO export exists, users should see it as a first-class output format, not as an undocumented extra artifact.

## Scope
- Update README usage/output sections.
- Update architecture/backlog references to export formats.
- Update generated folder guides so APO files are explained.
- Keep the wording simple for non-technical users.

## Out of scope
- New export implementations beyond APO.
- GUI redesign.

## Acceptance criteria
- README mentions APO export in the main workflow/output sections.
- Output folder guides mention the APO preset file.
- Backlog reflects APO export as shipped once implemented.

## Suggested files/components
- `README.md`
- `docs/architecture.md`
- `docs/backlog.md`
- `headmatch/pipeline.py`
