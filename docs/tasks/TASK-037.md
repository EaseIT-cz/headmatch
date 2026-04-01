# TASK-037 — Add a simple CLI environment diagnostics command

## Summary
Add a small diagnostics command that helps users quickly verify whether their local HeadMatch environment is ready, especially for PipeWire-based measurement.

## Context
The next active backlog item is installation and release ergonomics. A small CLI diagnostics slice is the most practical first step: it can reduce setup friction without requiring packaging or launcher redesign first.

## Scope
- Add a simple CLI diagnostics command, such as `headmatch doctor`, for local environment checks.
- Report the most useful basics clearly, such as required executables, config path, and PipeWire discovery availability.
- Keep the output beginner-friendly and actionable.
- Update tests as needed.

## Out of scope
- Installer packaging changes.
- Full GUI diagnostics workflow.
- Deep system probing beyond a small practical set of checks.
- Non-Linux platform support redesign.

## Acceptance criteria
- Users can run one command to get a quick environment readiness summary.
- Missing dependencies or likely setup blockers are reported clearly.
- The implementation is small and maintainable.
- Full test suite passes.

## Suggested files/components
- `headmatch/cli.py`
- `headmatch/measure.py`
- `headmatch/settings.py` if needed
- `tests/test_cli.py`
- `tests/test_measure.py` if needed
