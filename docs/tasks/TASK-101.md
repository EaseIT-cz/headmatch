# TASK-101: GUI Basic Mode Wizard

## Summary
Implement a guided, step-by-step "Basic Mode" wizard for users who want simple headphone EQ without exposed complexity.

## Context
The GUI currently exposes all options to all users. Beginners are overwhelmed. We need a separate "Basic Mode" that walks users through a 3-step measurement workflow with sensible defaults.

## Scope
- Add mode switcher to GUI navigation (Basic / Advanced)
- Implement Basic Mode as a 3-step wizard:
  1. **Target selection** — choose CSV, search database, or use flat (default)
  2. **Measurement** — 3 iterations, averaged, using default playback/capture devices
  3. **Review & Export** — show result, max 10 PEQ filters, one-click export
- Store mode preference in config
- Basic Mode uses hardcoded safe defaults:
  - Sample rate: 48kHz
  - Iterations: 3
  - Max PEQ filters: 10
  - Default output directory
- No advanced options visible in Basic Mode

## Out of Scope
- Changing default values in Basic Mode (that's Advanced)
- Mic calibration workflow (separate task)
- EQ clipping display (separate task)

## Acceptance Criteria
- [ ] User can switch between Basic and Advanced modes
- [ ] Basic Mode presents exactly 3 wizard steps
- [ ] Basic Mode completes a full measurement workflow
- [ ] Mode preference persists across sessions
- [ ] Basic Mode does not expose device selection, sweep parameters, or filter limits

## Suggested Files
- `headmatch/gui.py` — mode switcher, wizard views
- `headmatch/config.py` — mode preference storage
- `headmatch/defaults.py` (new) — Basic Mode defaults