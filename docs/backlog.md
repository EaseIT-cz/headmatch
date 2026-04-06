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

- **Dense GraphicEQ clipping**: May still clip in real-world use. Added 1.5 dB headroom but needs validation.
- **macOS real-hardware testing**: End-to-end testing on macOS with real audio hardware. CI passes but needs manual validation.

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
