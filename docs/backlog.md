# HeadMatch Backlog

**Version**: 0.6.2  
**Tests**: 523 passing across Linux/macOS

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
- **Basic Mode wizard** — guided 3-step workflow for beginners
- **GUI clipping display** — preamp recommendations in completion panel
- **CLI clipping output** — `--show-clipping` and `--json` flags
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save with field name migration
- Standalone binaries: Linux x64, macOS ARM64

---

## Blocked / On Hold

- **Dense GraphicEQ clipping**: May still clip in real-world use. Added 1.5 dB headroom but needs validation.
- **macOS real-hardware testing**: End-to-end testing on macOS with real audio hardware. CI passes but needs manual validation.

---

## Now

Nothing in progress. Awaiting next priorities.

---

## Done (v0.6.2)

- **TASK-101: GUI Basic Mode Wizard** — Guided 3-step workflow for beginners. Flat target default, 3 iterations, max 10 PEQ filters, no exposed complexity.
- **TASK-102: GUI Shell/View Refactoring** — Extracted shell into `gui/shell.py`, views remain in `gui_views.py`. gui.py reduced to 37-line re-export.
- **TASK-103: Clone-Target Calibration Docs** — Documented clone-target workflow as mic calibration technique.
- **TASK-104: EQ Clipping GUI Display** — Preamp recommendations in GUI completion panel with warning indicator.
- **TASK-105: EQ Clipping CLI Output** — Clipping summary in `headmatch fit` with `--show-clipping` and `--json` flags.

---

## Next

### Priority 1: Mic calibration roadmap

- **Mic calibration workflow** — Long-term: derive mic response curve via trusted data comparison. Requires research on:
  - Which published measurement databases are reliable
  - How to handle ear canal resonance variation
  - Whether per-user calibration is tractable

### Priority 2: GUI refactoring backlog

- **TASK-106: Split gui_views.py into real per-view modules**
- **TASK-107: Extract GUI workflow controllers from HeadMatchGuiApp**
- **TASK-108: Centralize GUI file-picking and background task helpers**
- **TASK-109: Replace shell view dispatch with registry-based routing**
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
