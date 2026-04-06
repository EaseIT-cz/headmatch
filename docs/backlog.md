# HeadMatch Backlog

**Version**: 0.6.1rc2 (dev branch)
**Branch protection**: main requires PR; work on dev

---

## Blocked

### TASK-091: Linux binary distribution
**Status**: ⚠️ Blocked — OpenBLAS runtime issue  
**Priority**: High  
**Assignee**: dev1

PyInstaller build completes but runtime fails with ELF page-alignment error from bundled OpenBLAS.

**Resolution options**:
- Pin numpy<2.4 in requirements
- Build in manylinux container
- Use conda-forge numpy with system BLAS

---

## Ready

### TASK-077: GraphicEQ clipping research
**Status**: 📋 Ready  
**Priority**: Medium

Dense GraphicEQ export still clips despite 0.4.4 fix. Investigate PEQ-fitted response at high PPO.

**Scope**: Research, may become multiple implementation tasks.

### TASK-090: macOS integration testing
**Status**: 📋 Ready  
**Priority**: Medium

End-to-end testing on macOS with real hardware. Requires macOS machine access.

### TASK-092: macOS binary distribution
**Status**: 📋 Ready (after TASK-091)  
**Priority**: High

Blocked by TASK-091 binary infrastructure.

### TASK-093: Product pages placeholder
**Status**: 📋 Ready  
**Priority**: Low

Add `docs/product_pages.md` placeholder file.

### TASK-096: Target editor binary bug
**Status**: 📋 Ready  
**Priority**: High

Target editor broken in 0.6.1rc1 Linux binary. Likely missing resources in PyInstaller spec.

---

## Completed (2026-04-06)

- TASK-094: GitHub issue templates
- TASK-095: EQ clipping prediction
- TASK-097: Docstring drift fix
- TASK-098: Release-gate CI workflow
