# TASK-043 — Reduce overflowing GUI helper copy and improve native theme adoption

## Summary
Clean up the remaining overflowing descriptive copy in the GUI and improve how the Tk/ttk app follows the host OS theme.

## Context
The recent GUI simplification improved navigation, but some descriptive/helper text still overflows awkwardly in the form areas. The user is testing under KDE on Wayland and wants the app to feel more native. Because HeadMatch uses Tk/ttk, full KDE-native theming is limited, but the app should still rely on the active ttk theme, avoid fighting system defaults, and use more appropriate sizing/spacing.

## Scope
- Remove or shorten overflowing descriptive/helper text in the GUI forms where it does not fit well.
- Improve native-theme adoption using Tk/ttk-friendly approaches.
- Prefer system/default colors, fonts, and widget styling where practical.
- Keep the change GUI-only.
- Update tests as needed.

## Out of scope
- Rewriting the GUI toolkit.
- Custom KDE integration beyond what Tk/ttk can support.
- Backend, CLI, or TUI changes.
- Broad GUI redesign.

## Acceptance criteria
- GUI helper text no longer overflows awkwardly in the affected areas.
- The app relies more cleanly on the active OS/ttk theme.
- Styling changes remain conservative and maintainable.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
