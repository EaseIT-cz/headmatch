# TASK-053 — Add GUI file and folder pickers for path fields

## Summary
Improve the GUI by adding file/folder picker controls for the main path-based fields such as output directory, target CSV, and recorded WAV.

## Context
The GUI currently relies on manual text entry for important filesystem paths. That is workable, but it is slower and more error-prone than native file/folder pickers. The user wants direct pickers for fields like output directory, target CSV, and recorded WAV while keeping the GUI simple.

## Scope
- Add native file/folder picker controls to the relevant GUI forms.
- Cover at least:
  - output directory
  - target CSV
  - recorded WAV for offline fit/import flows
- Keep manual entry available alongside the picker.
- Preserve existing backend behavior and saved-config behavior.
- Update tests as needed.

## Out of scope
- Broad GUI redesign.
- Backend measurement changes.
- CLI/TUI changes.
- New settings/preferences beyond what existing fields already store.

## Acceptance criteria
- GUI users can browse for the major path inputs instead of typing them manually.
- Manual editing still works.
- The implementation is conservative and consistent across relevant views.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
