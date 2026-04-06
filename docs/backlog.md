# HeadMatch Backlog

**Version**: 0.6.1  
**Tests**: 520+ passing across Linux/macOS

---

## Capabilities

- Cross-platform: Linux (PipeWire), macOS (PortAudio), Windows (experimental)
- GUI-first headphone measurement and EQ tool (CLI + TUI also supported)
- Pluggable audio backend architecture
- Real-time frequency response measurement
- Live curve preview in target editor with canvas drag-to-move
- Conservative PEQ fitting with Nelder-Mead refinement
- APO import with refine mode (CLI + GUI)
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- Confidence scoring with plain-language interpretation
- EQ clipping prediction with preamp recommendations
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save with field name migration
- Standalone binaries: Linux x64, macOS ARM64

---

## Blocked / On Hold

### TASK-077: Dense GraphicEQ clipping
**Status**: On hold (awaiting user testing)  
**Summary**: Dense GraphicEQ export may still clip in real-world use. Added 1.5 dB headroom but needs validation.

### TASK-090: macOS real-hardware testing
**Status**: Blocked (requires hardware access)  
**Summary**: End-to-end testing on macOS with real audio hardware. CI passes but needs manual validation.

---

## Now

Nothing in progress. Awaiting next priorities.

---

## Next

- GUI display for EQ clipping assessment
- CLI output for clipping summary
- GUI shell/view split — gui.py is ~880 lines
- Extract repeated CLI parser setup into shared helpers
- Richer per-backend error diagnostics

---

## Later

- macOS .app bundle (currently distributed as raw binary)
- Windows .exe binary via PyInstaller
- AppImage wrapper for Linux
- Target editor polish — keyboard shortcuts, undo/redo
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Additional export formats (beyond CamillaDSP and APO)
- CamillaDSP live-update via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure)
- Room correction / speaker measurement mode
- Asynchronous device support / clock drift compensation
- Automated HRTF target integration
- Safe mode vs advanced mode UI split

---

## Completed (v0.6.1)

### TASK-091: Linux x64 binary
Fixed OpenBLAS ELF alignment by pinning numpy<2, scipy<1.14. Added scipy.interpolate to hiddenimports.

### TASK-092: macOS binary workflow  
ARM64 binary builds in CI. Intel build removed (simplified to ARM64 only).

### TASK-093: Product pages placeholder
Created `docs/product_pages.md`.

### TASK-094: GitHub issue templates
Bug report and feature request templates.

### TASK-095: EQ clipping prediction
Predictive clipping assessment, preamp calculation, quality warnings.

### TASK-096: Target editor binary bug
Fixed missing scipy.interpolate in PyInstaller hiddenimports.

### TASK-097: Docstring drift
Fixed in measure.py and audio_backend.py.

### TASK-098: Release-gate workflow
sdist build + test before release.

---

## Process Notes

- Binary builds require platform-specific hiddenimports (scipy.interpolate, sounddevice)
- macOS tests need platform-specific skips for PipeWire-specific tests
- MANIFEST.in updated for docs/examples and tests/fixtures
- Tests verified against built sdist
