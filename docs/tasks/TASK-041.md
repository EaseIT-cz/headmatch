# TASK-041 — Add a simple desktop-launcher/install note for the GUI

## Summary
Reduce friction for GUI-first users by adding a small, practical launcher/install note or asset that makes `headmatch-gui` easier to discover and start from a desktop environment.

## Context
The active backlog area is still installation and release ergonomics. HeadMatch is GUI-first, but the repo still assumes a fairly terminal-oriented launch path. A small launcher/documentation slice is a sensible next step.

## Scope
- Add a small, practical launcher-oriented improvement for GUI-first users.
- This can be an install note, a desktop entry example, or similarly lightweight packaging-adjacent asset.
- Keep the change conservative and easy to maintain.
- Update docs/tests as needed.

## Out of scope
- Full packaging/release automation redesign.
- Cross-distro installer support.
- Major GUI changes.
- New backend behavior.

## Acceptance criteria
- GUI-first users have a clearer path to launching HeadMatch outside a raw terminal command.
- The solution is lightweight and appropriate for the current repo scope.
- Docs/assets stay tidy and understandable.

## Suggested files/components
- `README.md`
- a lightweight launcher asset or example file if appropriate
- `docs/` if needed
