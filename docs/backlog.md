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
- Fixed iteration_mode not passed through CLI to pipeline
- Fixed import-apo to actually re-export imported bands
- Fixed Windows shell=True security issue in graph opener
- Tightened fetch-curve to HTTPS-only with 5 MB response cap
- Added tests/__init__.py for sdist compatibility
- Merged duplicate fit/fit-offline CLI branches
- Made search-headphone honest about being a placeholder
- Added user-friendly JSON config error messages
- Added positive-int validators for --iterations and --max-filters

### 0.4.0
- Vectorised fractional-octave smoothing (~50× faster)
- Direct biquad evaluation replacing scipy.signal.freqz (3-5× faster)
- APO AutoEQ preset import
- Community headphone database integration
- GUI target curve editor with PCHIP interpolation

### 0.3.0
- Wiener regularisation, raw residual Q, local-maxima alignment, joint PEQ refinement
- Confidence badges in GUI, verdict line in CLI, scrollable diagnostics
- Graph display button in GUI results view
- Multi-pass averaging iteration mode
- RBJ coefficient reference tests and biquad stability tests
- Fixed _metrics dead mask, alignment_peak_ratio, shelf Q/S export
- Removed dead code, added plots.py and signals.py test coverage
- Type-narrowed PEQBand.kind, extracted confidence constants, injectable weights

### 0.2.3
- Mono and duplicated-channel capture rejection (including multichannel)

### 0.2.2
- Fixed-band GraphicEQ fitting and expanded regression tests

## Future follow-up candidates

### Code quality / consistency
- Use encoding="utf-8" consistently for all read_text() / write_text() calls
- Extract repeated CLI parser setup into shared helpers
- Improve GUI/CLI/TUI shared plumbing — advanced options are CLI-first, GUI lags
- Add pytest.ini with pythonpath config and verify MANIFEST.in include rules

### Features
- Add export formats beyond CamillaDSP and APO if users actually need them
- Implement import-apo refine mode (re-optimise imported preset against user measurement)
- Implement real headphone database search (GitHub API or cached local index)
- Cache fixed-profile basis responses for repeated runs
- Add richer PipeWire error diagnostics (show exact command and target names)

### Testing / CI
- Add explicit Python 3.10–3.13 CI matrix
- Verify sdist / wheel build produces a self-consistent test-runnable package
- Add content-type validation to fetch-curve responses

### Compatibility
- Consistent cross-platform file-open (os.startfile / open / xdg-open) across all paths
- Consider streaming with size cap for all network fetches

## Future feature candidates (deferred)

1. Asynchronous device support and clock drift compensation
2. Automated HRTF target integration and scaling
3. CamillaDSP live-update integration via WebSocket API
4. Closed-loop EQ refinement (measure → apply → re-measure; depends on #3)
5. Windows/macOS support (platform-aware measure.py backends)
6. Room correction / speaker measurement mode
