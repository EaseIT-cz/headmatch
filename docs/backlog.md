# HeadMatch backlog

## Current status

Version 0.5.0 shipped. 436 deterministic tests.

Key capabilities:
- GUI-first headphone measurement and EQ tool (CLI + TUI also supported)
- Real headphone database search via GitHub API with local cache
- Live curve preview in target editor
- Conservative PEQ fitting with Nelder-Mead refinement
- APO import with refine mode (re-optimise against a fresh measurement)
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- Confidence scoring with plain-language interpretation
- CI matrix across Python 3.10–3.13

## Active

### On hold
- TASK-077: Research and fix dense GraphicEQ clipping (awaiting user testing)

## Future work

### Now
- GUI refine-apo view (wire refine-apo into the GUI Import APO screen)

### Next (medium-term improvements)
- Drag-to-move control points on target editor canvas
- GUI shell/view split — extract view rendering from gui.py monolith into smaller components
- Extract repeated CLI parser setup into shared helpers
- Cache fixed-profile basis responses for repeated GraphicEQ runs
- Add CI coverage reporting as artifact
- Add richer PipeWire error diagnostics (device not found, permission denied, timeout)
- Deprecate fit-offline alias (keep code path, warn on use)

### Later (strategic / larger scope)
- Add export formats beyond CamillaDSP and APO if demand exists
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure; depends on CamillaDSP WebSocket)
- Windows/macOS support (platform-aware measure.py backends)
- Room correction / speaker measurement mode
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- Safe mode vs advanced mode UI split (if product accumulates too many knobs)
