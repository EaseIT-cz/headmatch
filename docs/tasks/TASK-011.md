# TASK-011 — Implement the GUI measurement wizard

## Summary
Add the beginner-oriented online and offline measurement flows in the GUI.

## Context
Once the shell exists, the GUI needs the actual end-user workflow: measurement, fit, and completion.

## Scope
- Implement guided online measurement.
- Implement offline fallback flow.
- Show progress and completion screens.
- Connect the wizard to the shared pipeline.

## Out of scope
- History browser.
- Non-essential customization.

## Acceptance criteria
- A user can complete the primary workflow in the GUI.
- The offline fallback is available.
- The GUI clearly communicates what it is doing and what to do next.

## Suggested files/components
- future `headmatch/gui.py`
- `headmatch/pipeline.py`
- `headmatch/measure.py`
- `headmatch/targets.py`
- tests
