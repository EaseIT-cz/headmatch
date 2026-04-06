# TASK-091: Linux binary distribution (PyInstaller)

**Status**: 🔧 Fix prepared — needs rebuild

**Summary**: Produce a Linux x86_64 single-file executable for HeadMatch.

## Context

Users without Python need a standalone binary. PyInstaller bundles Python, dependencies, and the app into a single executable.

## Problem

NumPy 2.4.x bundles OpenBLAS with ELF page alignment incompatible with older kernels/loaders:
```
ImportError: libscipy_openblas64_-32a4b2a6.so: ELF load command address/offset not page-aligned
```

## Fix Applied

Pinned `numpy<2.4` in `pyproject.toml`. NumPy 2.2.x and earlier use OpenBLAS without this issue.

## Scope

- [x] Validate spec file exists (`headmatch.spec`)
- [x] Confirm tkinter is available (python3-tk)
- [x] Confirm python3-dev is available
- [x] Install PyInstaller in sandbox
- [x] Build both CLI and GUI binaries
- [x] Pin numpy<2.4 to fix OpenBLAS issue
- [ ] Rebuild binary and test
- [ ] Upload to GitHub releases

## Build Command

```bash
cd /shared/headmatch
# Reinstall pinned numpy
/shared/headmatch/.venv/bin/pip install 'numpy<2.4'
# Rebuild
XDG_CACHE_HOME=/tmp/cache HOME=/tmp \
  PYTHONPATH=/tmp/pylibs \
  /shared/headmatch/.venv/bin/python -m PyInstaller headmatch.spec \
  --noconfirm --workpath=/tmp/build --distpath=/tmp/dist
```

## Acceptance Criteria

- [ ] Binary builds without errors
- [ ] Binary runs `--version` successfully
- [ ] Binary handles basic commands without scipy import errors
