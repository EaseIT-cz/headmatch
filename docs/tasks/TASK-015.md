# TASK-015 — Decide config location and first-run behavior

## Summary
Pick where user settings live and define what happens when no config exists yet.

## Context
Persistence is only useful if the default location and first-run behavior are predictable. This needs to be defined before the TUI and GUI start relying on it.

## Scope
- Choose a default config path.
- Define first-run file creation behavior.
- Document safe defaults when the config is missing.
- Make the policy consistent across CLI, TUI, and GUI.

## Out of scope
- Full GUI settings editor.
- Device autodiscovery redesign.

## Acceptance criteria
- The default config path is documented.
- First-run behavior is defined and implemented.
- Missing config falls back to safe defaults.
- The policy is shared across all frontends.

## Suggested files/components
- `docs/architecture.md`
- `docs/backlog.md`
- new settings module
- `README.md`
