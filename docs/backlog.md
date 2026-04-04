# HeadMatch backlog

## Current status

The shipped product includes:
- CLI with one-line confidence verdict, positive-int validation, user-friendly error messages
- GUI with confidence badges, graph display, scrollable diagnostics, target editor (load/save/edit), APO import, curve fetch, iteration mode selector, desktop shortcut management
- TUI backup workflow (maintenance-only)
- APO AutoEQ preset import and re-export
- Community headphone database search guidance and HTTPS-only curve fetching
- Multi-pass averaging iteration mode
- Conservative PEQ fitting with joint Nelder-Mead refinement
- Wiener-regularised frequency response estimation
- Local-maxima alignment search (robust to room echoes)
- Raw residual bandwidth estimation for accurate narrow-feature Q
- Vectorised fractional-octave smoothing and direct biquad evaluation
- Equalizer APO parametric and GraphicEQ preset export
- CamillaDSP export with correct shelf Q/S conversion
- Fixed-band GraphicEQ fitting (10-band and 31-band profiles)
- Clone-target support with explicit relative/absolute semantics
- Mono and duplicated-channel capture rejection (all channel counts)
- Confidence scoring with named threshold constants and injectable weights
- Type-safe PEQBand.kind (Literal)
- Desktop shortcut management (CLI + GUI)
- CI with explicit least-privilege permissions and auto-discovery of test files
- 401 deterministic tests including 241 RBJ biquad coefficient reference tests

## Active

- TASK-077: Research and fix dense GraphicEQ clipping
- TASK-078: Live curve preview in the target editor
- TASK-079: Real headphone database search

## Future work

### Next
- Add pytest.ini with pythonpath config
- Verify MANIFEST.in / setuptools include rules for sdist
- Add Python 3.10–3.13 CI matrix
- Use encoding="utf-8" consistently across all file I/O

### Later
- Extract repeated CLI parser setup into shared helpers
- Cache fixed-profile basis responses for repeated runs
- Add richer PipeWire error diagnostics
- Add export formats beyond CamillaDSP and APO if demand exists
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (depends on CamillaDSP WebSocket)
- Windows/macOS support (platform-aware measure.py backends)
- Room correction / speaker measurement mode
