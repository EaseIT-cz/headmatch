# TASK-061 — Add confidence badge styling to GUI history view

## Summary
The GUI history view shows confidence as plain text. Add visual differentiation so users can scan results at a glance.

## Context
`render_history_results` in `gui_views.py` already displays confidence label, score, headline, and interpretation. But all text uses the same style. A color or icon hint for high/medium/low confidence would make the history list scannable without reading every line.

## Scope
- Add a styled confidence indicator (color-coded label or prefix icon) to the history list entries and the selected-run detail card.
- Use tkinter ttk style maps — green/yellow/red text or a unicode prefix (✓ / ⚠ / ✗).
- Keep it simple: no custom widgets, no images.

## Out of scope
- Changing confidence scoring logic.
- Redesigning the history layout.
- Adding new confidence fields.

## Acceptance criteria
- High confidence runs show a visually distinct positive indicator.
- Low confidence runs show a visually distinct warning indicator.
- Medium confidence is distinguishable from both.
- Existing GUI tests pass.
- No new dependencies.

## Suggested files/components
- `headmatch/gui_views.py`
- `headmatch/gui.py` (style registration)
- `tests/test_gui.py`
