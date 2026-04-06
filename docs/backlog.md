# HeadMatch Backlog

**Version**: 0.6.1rc2 (dev branch)

---

## Blocked

### TASK-091: Linux binary distribution
**Status**: ⚠️ Blocked — OpenBLAS runtime issue  
**Priority**: High

PyInstaller build completes but runtime fails with ELF page-alignment error.

**Resolution options**:
- Pin numpy<2.4 in requirements
- Build in manylinux container
- Use conda-forge numpy with system BLAS

### TASK-092: macOS binary distribution
**Status**: ☑️ Blocked by TASK-091  
**Priority**: High

---

## Ready

### TASK-090: macOS integration testing
**Status**: 📋 Ready  
**Priority**: Medium

### TASK-096: Target editor binary bug
**Status**: 📋 Ready (blocked by TASK-091 for testing)  
**Priority**: High

---

## Completed (2026-04-06)

- TASK-077: GraphicEQ clipping fix (interpolation headroom)
- TASK-093: Product pages placeholder
- TASK-094: GitHub issue templates
- TASK-095: EQ clipping prediction
- TASK-097: Docstring drift fix
- TASK-098: Release-gate CI workflow
