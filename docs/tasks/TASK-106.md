# TASK-106 - Split gui_views.py into real per-view modules

## Summary
Break `headmatch/gui_views.py` into real per-view modules under `headmatch/gui/views/` and keep behavior unchanged.

## Context
The GUI refactor created `gui/shell.py`, but `gui_views.py` is still a large shared dump of unrelated view renderers and helper functions. This prevents small, isolated changes and increases merge risk.

## Scope
- Move view renderers from `headmatch/gui_views.py` into real modules under `headmatch/gui/views/`
- Extract shared row/picker/form helpers into `headmatch/gui/views/common.py`
- Keep `_PlotGeometry` and target-editor-specific rendering in `headmatch/gui/views/target_editor.py`
- Update imports/exports so external call sites remain stable
- Preserve backward compatibility where practical
- Add/update tests for imports and core GUI render paths

## Out of scope
- Redesigning workflows
- Changing backend logic
- Reworking app state model
- Replacing routing in `gui/shell.py`

## Acceptance criteria
- `headmatch/gui_views.py` is reduced to a thin compatibility layer or removed entirely
- Real modules exist for the major view families
- GUI tests pass unchanged or improved
- No behavior regressions in rendered screens

## Suggested files/components
- `headmatch/gui_views.py`
- `headmatch/gui/views/common.py`
- `headmatch/gui/views/basic.py`
- `headmatch/gui/views/completion.py`
- `headmatch/gui/views/fetch_curve.py`
- `headmatch/gui/views/history.py`
- `headmatch/gui/views/import_apo.py`
- `headmatch/gui/views/offline.py`
- `headmatch/gui/views/online.py`
- `headmatch/gui/views/setup.py`
- `headmatch/gui/views/target_editor.py`
- `headmatch/gui/views/__init__.py`
- `tests/test_gui.py`
