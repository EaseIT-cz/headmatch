# TASK-091: Linux binary distribution (PyInstaller)

**Status**: ⚠️ Blocked — runtime OpenBLAS issue

**Assignee**: dev1

**Summary**: Produce a Linux x86_64 single-file executable for HeadMatch.

## Context

Users without Python need a standalone binary. PyInstaller bundles Python, dependencies, and the app into a single executable.

## Scope

- [x] Validate spec file exists (`headmatch.spec`)
- [x] Confirm tkinter is available (python3-tk)
- [x] Confirm python3-dev is available
- [x] Install PyInstaller in sandbox
- [x] Build both CLI and GUI binaries
- [ ] Fix runtime OpenBLAS ELF alignment issue
- [ ] Test binary on clean system
- [ ] Upload to GitHub releases

## Implementation

### Build Command

```bash
cd /shared/headmatch
XDG_CACHE_HOME=/tmp/cache HOME=/tmp \
  PYTHONPATH=/tmp/pylibs \
  /shared/headmatch/.venv/bin/python -m PyInstaller headmatch.spec \
  --noconfirm --workpath=/tmp/build --distpath=/tmp/dist
```

### Current Results

| Binary | Size | Status |
|--------|------|--------|
| `headmatch` | 56 MB | Build OK, runtime fails |
| `headmatch-gui` | 61 MB | Build OK, runtime fails |

### Runtime Error

```
ImportError: libscipy_openblas64_-32a4b2a6.so: ELF load command address/offset not page-aligned
```

**Cause**: NumPy 2.4.4 wheel bundles an OpenBLAS with page-alignment incompatibility on older kernels/loaders.

**Resolution Options**:
1. Pin numpy<2.4 in requirements
2. Use `--exclude-module` and system OpenBLAS
3. Build in manylinux Docker container
4. Use conda-forge numpy

## Acceptance Criteria

- [ ] Binary builds without errors
- [ ] Binary runs `--version` successfully
- [ ] Binary runs `headmatch doctor` successfully
- [ ] Binary size < 80 MB
- [ ] Works on Ubuntu 22.04+ and Fedora 38+

## Out of Scope

- macOS universal binary (TASK-092)
- Windows build
- Auto-update mechanism
- Code signing

## Files

- `headmatch.spec` — PyInstaller spec file
- `scripts/build.py` — Build orchestration (optional)

## Related

- TASK-092: macOS binary (depends on this)
