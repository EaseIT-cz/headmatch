# HeadMatch Backlog

**Version**: 0.6.1rc2 (dev branch)

---

## Ready

### TASK-090: macOS integration testing
**Status**: Ready  
**Priority**: Medium
**Summary**: Run integration tests on macOS hardware to verify audio backend compatibility.

---

## Completed (2026-04-06)

- **TASK-077**: GraphicEQ clipping fix — Added 1.5 dB interpolation headroom to prevent clipping in Equalizer APO
- **TASK-091**: Linux binary — Fixed OpenBLAS ELF alignment issue by pinning numpy<2, scipy<1.14 in CI
- **TASK-092**: macOS binary workflow — Added `build-macos` job to release-binary.yml
- **TASK-093**: Product pages — Placeholder documentation added
- **TASK-094**: GitHub issue templates — Already existed
- **TASK-095**: EQ clipping prediction — Feature implemented
- **TASK-096**: Target editor binary bug — Fixed by adding `scipy.interpolate` to PyInstaller hiddenimports
- **TASK-097**: Docstring drift — Fixed in measure.py and audio_backend.py
- **TASK-098**: Release-gate workflow — Already existed
