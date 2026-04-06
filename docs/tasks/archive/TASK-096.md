# TASK-096: Bug – Target editor broken in stand‑alone Linux binary

**Summary**: Fix the target editor crash/regression in the Linux stand‑alone binary.

**Context**: The recent binary release (0.6.1rc1) shows the target editor failing to load or interact, likely due to missing resources or path issues.

**Scope**:
- Reproduce the issue using the stand‑alone binary.
- Identify missing assets or incorrect relative paths.
- Adjust the binary build process to include required files (e.g., GUI resources, icons).
- Verify the target editor works end‑to‑end.

**Out‑of‑Scope**:
- Refactoring the entire target editor UI.
- Adding new features to the editor.

**Acceptance Criteria**:
- The target editor opens without errors in the Linux binary.
- All editor interactions (adding points, dragging, saving) function as in the development version.
- Automated test (if any) passes for the editor in binary mode.
- No regression introduced elsewhere.

**Suggested Files/Components**:
- `scripts/build.py` (ensure resources are packaged)
- `headmatch/gui.py` and `headmatch/gui_views.py` (path handling)
- Binary spec (`headmatch.spec`).
