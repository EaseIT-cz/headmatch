# HeadMatch backlog

## Current status

The shipped product includes:
- CLI with one-line confidence verdict, positive-int validation, user-friendly error messages
- GUI with confidence badges, graph display, scrollable diagnostics, target curve editor
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
- 392 deterministic tests including 241 RBJ biquad coefficient reference tests

## Active

No active tasks.

## Recently completed

### 0.4.0 patch
- Fixed iteration_mode not passed through CLI
- Fixed import-apo to actually re-export imported bands
- Fixed Windows shell=True security issue in graph opener
- Tightened fetch-curve to HTTPS-only with 5 MB cap
- Added tests/__init__.py for sdist compatibility
- Merged duplicate fit/fit-offline CLI branches
- Made search-headphone honest, added positive-int validators, config error handling

### 0.4.0
- Vectorised smoothing and direct biquad evaluation (performance)
- APO AutoEQ preset import
- Community headphone database integration
- GUI target curve editor with PCHIP interpolation

### 0.3.0
- Wiener regularisation, raw residual Q, local-maxima alignment, joint PEQ refinement
- GUI confidence badges, CLI verdict line, scrollable diagnostics, graph display
- Multi-pass averaging iteration mode
- RBJ coefficient tests, biquad stability tests
- Bug fixes: _metrics mask, alignment_peak_ratio, shelf Q/S, dead code removal

### 0.2.x
- Mono/duplicated-channel capture rejection
- Fixed-band GraphicEQ fitting and expanded regression tests

## Future work

### Now — GUI product parity and import-apo refine
- Wire target curve editor into GUI navigation
- Add import-apo and fetch-curve to GUI (currently CLI-only)
- Add iteration mode choice to GUI measurement wizard
- Implement import-apo --import-mode refine (re-optimise imported preset against user measurement)
- Implement real headphone database search (GitHub API or cached local index)

### Next — packaging and CI hardening
- Add pytest.ini with pythonpath config
- Verify MANIFEST.in / setuptools include rules for sdist
- Add Python 3.10–3.13 CI matrix
- Use encoding="utf-8" consistently across all file I/O
- Verify sdist / wheel produces self-consistent test-runnable package

### Later — polish and expansion
- Extract repeated CLI parser setup into shared helpers
- Cache fixed-profile basis responses for repeated runs
- Add richer PipeWire error diagnostics
- Add export formats beyond CamillaDSP and APO if demand exists
- Add content-type validation to fetch-curve responses
- Consistent cross-platform file-open across all paths
- Streaming with size cap for all network fetches
- Asynchronous device support and clock drift compensation
- Automated HRTF target integration and scaling
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (depends on CamillaDSP WebSocket)
- Windows/macOS support (platform-aware measure.py backends)
- Room correction / speaker measurement mode
