# HeadMatch backlog

## Current status

Version 0.5.0 shipped. 432 deterministic tests.

Key capabilities:
- GUI-first headphone measurement and EQ tool (CLI + TUI also supported)
- Real headphone database search via GitHub API with local cache
- Live curve preview in target editor
- Conservative PEQ fitting with Nelder-Mead refinement
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- Confidence scoring with plain-language interpretation

## Active

### On hold
- TASK-077: Research and fix dense GraphicEQ clipping (awaiting user testing)

## Future work

### Now (next release candidates)
- APO import "refine" mode — load an existing parametric preset and re-optimise against a fresh measurement (partially scaffolded in import-apo, needs fit integration)
- Python 3.10–3.13 CI matrix — validate compatibility beyond the current 3.13-only CI
- PipeWire capture pipe hardening — stdout→DEVNULL for pw-record, persist stderr to file for diagnosis

### Next (medium-term improvements)
- Drag-to-move control points on target editor canvas
- GUI shell/view split — extract view rendering from gui.py monolith into smaller components (flagged in architecture.md)
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
