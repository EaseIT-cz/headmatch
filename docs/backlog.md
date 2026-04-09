# HeadMatch Backlog

**Version**: 0.7.1 (post-code review)  
**Tests**: 618 passing across Linux/macOS  
**Coverage**: 80%

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
- **Batch-fit workflow** — process multiple recordings from JSON manifest (NEW in 0.7.1)
- **History & compare-runs** — CLI commands for reviewing past measurements (NEW in 0.7.1)
- **A/B comparison tool** — side-by-side EQ comparison with preset export (NEW in 0.7.1)
- **Confidence icons** — visual status indicators in CLI history output (NEW in 0.7.1)
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save with field name migration
- Standalone binaries: Linux x64, macOS ARM64

---

## Blocked / On Hold

- **Dense GraphicEQ clipping**: May still clip in real-world use. Added 1.5 dB headroom but needs validation.
- **macOS real-hardware testing**: End-to-end testing on macOS with real audio hardware. CI passes but needs manual validation.

---

## Now

Released 0.7.1. See RELEASE_NOTES-0.7.1.md.

---

## Done (0.7.1)

Code review delivered the following:

### Bug Fixes
- **BUG-001**: Removed invalid `output_target`/`input_target` properties from `RunFilterCounts` and `RunErrorSummary` (copy-paste error from `FrontendConfig`)
- **BUG-002**: Deduplicated set literals in CLI command routing
- **BUG-003**: Empty headphone search now returns `[]` instead of entire database
- **BUG-004**: Fixed file handle leak in PipeWire `play_and_record()`
- **BUG-005**: Added frequency-range validation for downloaded FR curves
- **BUG-006**: Removed spurious `pragma: no cover` from error handler with test coverage

### New Features
- **FEAT-001**: Batch-fit workflow (`headmatch batch-fit`, `headmatch batch-template`)
- **FEAT-002**: History and compare-runs CLI commands
- **FEAT-003**: A/B comparison tool with preset export (`headmatch compare-ab`)

### UI/UX Improvements
- **UI-001**: Basic-mode target guidance with dynamic help text
- **UI-002**: Missing-device guidance in online wizard (troubleshooting steps)
- **UI-003**: Confidence icons and clearer headers in history output

---

## Done (v0.7.0)

- **TASK-101: GUI Basic Mode Wizard** — Guided 3-step workflow for beginners. Flat target default, 3 iterations, max 10 PEQ filters, no exposed complexity.
- **TASK-102: GUI Shell/View Refactoring** — Extracted shell into `gui/shell.py`, views remain in `gui_views.py`. gui.py reduced to 37-line re-export.
- **TASK-103: Clone-Target Calibration Docs** — Documented clone-target workflow as mic calibration technique.
- **TASK-104: EQ Clipping GUI Display** — Preamp recommendations in GUI completion panel with warning indicator.
- **TASK-105: EQ Clipping CLI Output** — Clipping summary in `headmatch fit` with `--show-clipping` and `--json` flags.

---

## Done (v0.6.2)

All prior tasks completed. See release notes.

---

## Next

### Priority 1: Code Quality (from review)

- **TASK-109: Decompose gui/shell.py** — Extract `GuiState` into its own module, break out Tkinter variable initialization
- **TASK-110: Standardize error hierarchy** — Define `HeadMatchError` base class with `MeasurementError`, `ConfigError`, `NetworkError` subclasses
- **TASK-112: Add coverage CI gate** — Fail CI if coverage drops below 80%
- **TASK-113: Document confidence scoring derivation** — Add docstrings/design doc for `pipeline_confidence.py` magic numbers

### Priority 2: Security

- **TASK-114: URL validation in fetch_curve_from_url** — Consider domain allowlisting to prevent SSRF-like abuse

### Priority 3: GUI refactoring backlog

- **TASK-106: Split gui_views.py into real per-view modules**
- **TASK-107: Extract GUI workflow controllers from HeadMatchGuiApp**
- **TASK-108: Centralize GUI file-picking and background task helpers**

### Priority 4: Mic calibration roadmap

- **Mic calibration workflow** — Long-term: derive mic response curve via trusted data comparison. Requires research on:
  - Which published measurement databases are reliable
  - How to handle ear canal resonance variation
  - Whether per-user calibration is tractable

---

## Later

- **TASK-115: Async audio backend** — Replace `time.sleep()` synchronization with asyncio-based process management
- macOS .app bundle (currently distributed as raw binary)
- Windows .exe binary via PyInstaller
- AppImage wrapper for Linux
- Target editor polish — keyboard shortcuts, undo/redo
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Additional export formats (beyond CamillaDSP and APO)
- CamillaDSP live-update via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure)
- Room correction / speaker measurement mode
