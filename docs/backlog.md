# HeadMatch backlog

## Current status

Version 0.5.2 shipped. 447 deterministic tests.
Audio backend interface extracted (Phase 1 macOS support complete).

Key capabilities:
- GUI-first headphone measurement and EQ tool (CLI + TUI also supported)
- Real headphone database search via GitHub API with local cache
- Live curve preview in target editor with canvas drag-to-move
- Conservative PEQ fitting with Nelder-Mead refinement
- APO import with refine mode (CLI + GUI) — re-optimise against a fresh measurement
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- Confidence scoring with plain-language interpretation
- CI matrix across Python 3.10–3.13 with coverage reporting
- Pluggable audio backend architecture (PipeWire on Linux, PortAudio planned)

## Active

### On hold
- TASK-077: Research and fix dense GraphicEQ clipping (awaiting user testing)

### macOS support
- TASK-087: PortAudio audio backend (High — core enabler)
- TASK-088: Platform-aware config/cache paths (Medium)
- TASK-089: Platform-aware GUI/CLI text (Low — cosmetic)
- TASK-090: macOS integration testing and release (High — gates release, depends on 087)

## Future work

### Now
- TASK-087: PortAudio audio backend for macOS
- TASK-090: macOS integration testing and release (after 087)

### Next
- TASK-088: Platform-aware config/cache paths
- TASK-089: Platform-aware GUI/CLI text
- GUI shell/view split — gui.py is 865 lines; further extraction possible
- Extract repeated CLI parser setup into shared helpers
- Add richer error diagnostics per backend (device not found, permission denied, timeout)

### Later
- Further target editor polish — keyboard shortcuts, undo/redo for control point edits
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Add export formats beyond CamillaDSP and APO if demand exists
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure; depends on CamillaDSP WebSocket)
- Room correction / speaker measurement mode
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- Safe mode vs advanced mode UI split (if product accumulates too many knobs)
- Windows support (PortAudio backend works, needs testing + installer)
