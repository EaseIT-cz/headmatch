# HeadMatch backlog

## Current status

The shipped product includes:
- CLI with one-line confidence verdict, positive-int validation, user-friendly error messages
- GUI with confidence badges, graph display, scrollable diagnostics, target editor (load/save/edit), APO import, headphone database search, curve fetch, iteration mode selector, desktop shortcut management
- TUI backup workflow (maintenance-only)
- APO AutoEQ preset import and re-export
- Real headphone database search via GitHub API with local 24h cache
- HTTPS-only community curve fetching with 5 MB cap
- Multi-pass averaging iteration mode
- Conservative PEQ fitting with joint Nelder-Mead refinement
- Wiener-regularised frequency response estimation
- Local-maxima alignment search via scipy.signal.find_peaks (robust to room echoes)
- Raw residual bandwidth estimation for accurate narrow-feature Q
- O(N) fractional-octave smoothing via scipy gaussian_filter1d
- Direct biquad evaluation with explicit shelf slope/Q semantics
- Equalizer APO parametric and GraphicEQ preset export
- CamillaDSP export with correct shelf Q/S conversion
- Fixed-band GraphicEQ fitting (10-band and 31-band profiles)
- Clone-target support with explicit relative/absolute semantics
- Mono and duplicated-channel capture rejection (all channel counts)
- Confidence scoring with named threshold constants and injectable weights
- Type-safe PEQBand.kind (Literal) with explicit slope field for shelf bands
- Desktop shortcut management (CLI + GUI)
- CI with explicit least-privilege permissions and auto-discovery of test files
- Pipeline split into orchestration / artifacts / confidence modules
- 430 deterministic tests including 241 RBJ biquad coefficient reference tests

## Active

### High priority
- TASK-077: Research and fix dense GraphicEQ clipping (on hold — awaiting user testing)

### Medium priority
- TASK-078: Live curve preview in the target editor

## Future work

### Next
- Fix CHANGELOG header (still says "0.2.2 in development", should reflect 0.4.5)
- Add pytest.ini with pythonpath config
- Verify MANIFEST.in / setuptools include rules for sdist
- Add Python 3.10–3.13 CI matrix
- Use encoding="utf-8" consistently across all file I/O
- PipeWire capture pipe hardening (stdout→DEVNULL, stderr to file)
- Add CI coverage reporting as artifact
- APO import "refine" mode (re-optimise imported preset against a fresh measurement)

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
