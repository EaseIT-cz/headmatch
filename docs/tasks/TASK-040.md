# TASK-040 — Tighten beginner setup guidance around `doctor` and `list-targets`

## Summary
Improve the beginner-facing setup guidance so users are pointed toward `headmatch doctor` and `headmatch list-targets` at the moments when they are most useful.

## Context
HeadMatch now has both a setup diagnostics command and clearer PipeWire target guidance, but the user journey still relies on people discovering the right helper at the right time. A small copy/UX pass can make the setup path more self-correcting.

## Scope
- Improve beginner-facing guidance in CLI and/or GUI so users are nudged toward `doctor` when setup is uncertain and `list-targets` when device matching is unclear.
- Keep changes small and practical.
- Update tests as needed.

## Out of scope
- New diagnostics features.
- New PipeWire discovery behavior.
- GUI redesign.
- Broad docs rewrite.

## Acceptance criteria
- Beginner guidance points users to `doctor` and `list-targets` at useful decision points.
- The guidance is concise and non-technical.
- Existing behavior remains stable aside from the copy/UX improvements.
- Full test suite passes if code changes are made.

## Suggested files/components
- `headmatch/cli.py`
- `headmatch/gui_views.py`
- `tests/test_cli.py`
- `tests/test_gui.py`
