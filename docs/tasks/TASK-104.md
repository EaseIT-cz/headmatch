# TASK-104: EQ Clipping GUI Display

## Summary
Show EQ clipping assessment in the GUI completion panel so users can see preamp recommendations before exporting.

## Context
`assess_eq_clipping()` already computes preamp recommendations and warnings. This data is saved to the fit report but not surfaced in the GUI.

## Scope
- Add clipping summary to completion panel
- Display:
  - Preamp recommendation (dB)
  - Quality warnings (moderate/severe headroom loss)
  - Visual indicator (warning icon if clipping risk)
- Add preamp field to APO export when clipping detected
- Show assessed max boost in tooltip

## Out of Scope
- Changing clipping algorithm
- CLI output (separate task)
- Automatic preamp application (user decision)

## Acceptance Criteria
- [ ] Completion panel shows clipping assessment if available
- [ ] Preamp recommendation visible
- [ ] Warning indicator when headroom loss exceeds 6dB
- [ ] Export includes preamp when clipping risk present

## Suggested Files
- `headmatch/gui/views/completion.py` (after TASK-102)
- `headmatch/exporters/apo.py` — preamp field
- `headmatch/eq_clipping.py` — data source