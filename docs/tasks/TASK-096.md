# TASK-096: Bug – Target editor broken in stand‑alone Linux binary

**Status**: ✅ Fixed (2026-04-06)

**Summary**: Target editor crashed in Linux binary due to missing `scipy.interpolate` module.

**Root Cause**: PyInstaller's static analysis didn't detect the `from scipy.interpolate import PchipInterpolator` import in `target_editor.py`. The module was not bundled.

**Fix**: Added `'scipy.interpolate'` to `hiddenimports` in `headmatch.spec` for both GUI and CLI binaries.

**Verification**: Tested that TargetEditor and PchipInterpolator work correctly after rebuild.

**Files Modified**:
- `headmatch.spec` — Added `'scipy.interpolate'` to hiddenimports
