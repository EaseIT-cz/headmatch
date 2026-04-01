# TASK-002 — Add a beginner-first CLI wrapper

## Summary
Create a guided CLI flow that hides advanced options behind a simple default path.

## Context
The current CLI exposes low-level commands and many flags directly. That is fine for development, but it is too much surface area for the intended audience.

## Scope
- Introduce a single obvious entrypoint for first-run measurement.
- Reduce the number of required flags.
- Keep advanced flags available, but not as the primary experience.
- Print concise guidance after each command.

## Out of scope
- Fundamental changes to the measurement math.
- New GUIs.
- Cross-platform support.

## Acceptance criteria
- A user can complete the main workflow with minimal flags.
- The CLI output is understandable by a non-technical user.
- Help text reflects the beginner-first path.
- Existing developer-oriented commands still work.

## Suggested files/components
- `headmatch/cli.py`
- `headmatch/pipeline.py`
- `README.md`
