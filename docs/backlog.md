# HeadMatch backlog

## Current status

Version 0.6.1rc2 released. 520 tests.

Key capabilities:
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
- **EQ clipping prediction with preamp recommendations** (new in TASK-095)
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save with field name migration

## Active

### Released — 0.6.1rc1
- TASK-095: EQ clipping assessment — **completed** (predictive clipping, preamp calculation, quality concerns)
- TASK-097: Fix docstring drift in measure.py and audio_backend.py (new)
- TASK-098: Add release-gate job to verify sdist packaging (new)

### On hold
- TASK-077: Research and fix dense GraphicEQ clipping (awaiting user testing)
- TASK-090: macOS end-to-end measurement testing with real hardware

### Blocked — waiting for human host setup
- **TASK-091**: PyInstaller spec and build script for Linux x64 — requires host packages (`python3-tk`, `python3-dev`, mesa libs); see `docs/tasks/TASK-091.md`
- **TASK-092**: GitHub Actions workflow for Linux binary release — blocked by TASK-091

### In progress
- TASK-096: Target editor broken in stand‑alone Linux binary (reproduce and fix)

## Future work

### Now
- TASK-091: PyInstaller spec + build script (prepare host per TASK-091.md)
- TASK-092: GitHub Actions release workflow (blocked until 091 ready)

### Next
- GUI display for EQ clipping assessment
- CLI output for clipping summary
- GUI shell/view split — gui.py is ~880 lines
- Extract repeated CLI parser setup into shared helpers
- Richer per-backend error diagnostics

### Later
- macOS .app bundle via PyInstaller (build on macos-14 runner in CI)
- Windows .exe binary via PyInstaller (build on windows-latest runner in CI)
- AppImage wrapper for Linux (alternative to single binary)
- Further target editor polish — keyboard shortcuts, undo/redo
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Add export formats beyond CamillaDSP and APO if demand exists
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure)
- Room correction / speaker measurement mode
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- Safe mode vs advanced mode UI split

### Documentation
- TASK-093: Product pages placeholder for headmatch.github.io (requires repo GitHub Pages configuration)
- `docs/feature_eq_clipping.md` — document EQ clipping prediction feature

### Features
- EQ clipping assessment — completed; GUI/CLI display pending

## Process improvements

### Completed
- TASK-094: GitHub issue templates — **completed** (`.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`)
- TASK-095: EQ clipping prediction — **completed** (`headmatch/eq_clipping.py`, integrated into `pipeline.py`, 13 tests)
- MANIFEST.in updated to include `docs/examples/*.csv *.json *.desktop` and `tests/fixtures/*`
- Tests verified against built sdist (520 tests pass)
