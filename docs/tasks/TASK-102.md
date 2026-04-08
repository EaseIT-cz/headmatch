# TASK-102: GUI Shell/View Refactoring

## Summary
Extract view rendering and shell layout from `gui.py` into separate modules to improve maintainability and enable parallel development.

## Context
`gui.py` is 920 lines and growing. It mixes shell concerns (navigation, state, wiring) with view rendering (forms, buttons, output). This makes the file hard to navigate and risky to modify.

## Scope
- Create `headmatch/gui/` package directory
- Extract view modules:
  - `gui/shell.py` — main app shell, navigation, mode switching
  - `gui/views/basic_wizard.py` — Basic Mode wizard steps
  - `gui/views/advanced_panel.py` — Advanced Mode controls
  - `gui/views/target_editor.py` — target curve editor
  - `gui/views/import_apo.py` — APO import/refine workflow
  - `gui/views/history.py` — run history browser
  - `gui/views/completion.py` — results and export
- Keep `HeadMatchGuiApp` class as the coordinator
- Maintain backward compatibility for existing tests

## Out of Scope
- Changing GUI behavior or workflow
- Adding new features
- TUI refactoring

## Acceptance Criteria
- [ ] `gui.py` reduced to ~200 lines (shell + coordination)
- [ ] All views extracted to `gui/views/`
- [ ] All existing tests pass
- [ ] Imports still work via `from headmatch.gui import ...`

## Suggested Files
- `headmatch/gui.py` → `headmatch/gui/shell.py`
- `headmatch/gui/` (new package)
- `headmatch/gui/views/` (new package)