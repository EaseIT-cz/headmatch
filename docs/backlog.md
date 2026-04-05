# HeadMatch backlog

## Current status

Version 0.6.0 shipped. 507 deterministic tests.

Key capabilities:
- Cross-platform: Linux (PipeWire), macOS (PortAudio), Windows (experimental)
- GUI-first headphone measurement and EQ tool (CLI + TUI also supported)
- Pluggable audio backend architecture
- Real headphone database search with space-insensitive matching
- Live curve preview in target editor with canvas drag-to-move
- Conservative PEQ fitting with Nelder-Mead refinement
- APO import with refine mode (CLI + GUI)
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- Confidence scoring with plain-language interpretation
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save with field name migration

## Active

### On hold
- TASK-077: Research and fix dense GraphicEQ clipping (awaiting user testing)
- TASK-090: macOS end-to-end measurement testing with real hardware

## Future work

### Now
- (no blockers — ready for next feature work)

### Next
- GUI shell/view split — gui.py is ~880 lines; further extraction possible
- Extract repeated CLI parser setup into shared helpers
- Richer per-backend error diagnostics (device not found, permission denied, timeout)

### Later
- Further target editor polish — keyboard shortcuts, undo/redo
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Add export formats beyond CamillaDSP and APO if demand exists
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure)
- Room correction / speaker measurement mode
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- Safe mode vs advanced mode UI split
- Windows installer and testing
