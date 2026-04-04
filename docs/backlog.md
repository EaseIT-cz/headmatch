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

- TASK-077: Research and fix dense GraphicEQ clipping (feature considered broken)

## Recently completed

### 0.4.5
- Fixed target editor `from_csv` to load all points from small CSVs and intelligently downsample dense grids to ~24 control points (was hardcoded to 8)

### 0.4.4
- Dense GraphicEQ export changed from raw target to PEQ-fitted response (partial clipping fix — still under investigation)
- Target editor: per-row "+" add button, "Load CSV" button
- History view: "Browse…" button for search folder
- Desktop shortcut management (`create-shortcut`, `remove-shortcut`, GUI toggle, doctor integration)
- 7 new desktop.py tests, 2 new target_editor tests
- CI: explicit permissions on all workflows, pytest auto-discovers test files

### 0.4.1
- Fixed `--iteration-mode` CLI passthrough, import-apo behavior, Windows security, fetch-curve validation
- GUI feature parity: target editor, APO import, curve fetch, iteration mode views
- Merged fit/fit-offline, positive-int validators, config error handling

### 0.4.0
- Vectorised smoothing and direct biquad evaluation (performance)
- APO AutoEQ preset import, headphone database integration, GUI target editor

### 0.3.0
- Wiener regularisation, raw residual Q, local-maxima alignment, joint PEQ refinement
- GUI confidence badges, CLI verdict, graph display, averaging iteration mode
- RBJ coefficient tests, biquad stability tests, bug fixes

### 0.2.x
- Mono/duplicated-channel capture rejection, GraphicEQ fitting

## Future work

### Now
- TASK-077: Research and fix dense GraphicEQ clipping
- Live curve preview in the target editor
- Implement real headphone database search

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
