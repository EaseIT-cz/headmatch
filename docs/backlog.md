# HeadMatch backlog

## Current status

The current shipped state includes:
- beginner-first CLI workflow with one-line confidence verdict
- GUI shell with confidence badges, graph display, scrollable diagnostics
- TUI backup workflow and history browsing (maintenance-only)
- shared settings persistence and preload
- improved capture/import robustness (mono, duplicated-channel, multichannel)
- stronger alignment robustness coverage
- conservative PEQ/export polish
- clone examples and cross-source validation
- deterministic end-to-end synthetic integration tests (373 tests)
- RBJ reference coefficient verification (241 parametric tests)
- biquad numerical stability verification for extreme parameters
- GitHub Actions coverage for both main and integration test suites
- PipeWire device guidance
- measured-vs-target graph rendering
- Equalizer APO-compatible parametric and GraphicEQ preset export
- CamillaDSP export with correct shelf Q conversion
- confidence / trust summaries in fit outputs
- fixed-band GraphicEQ fitting support (10-band and 31-band profiles)
- multi-pass averaging iteration mode

## Active

No active tasks.

## Recently completed (0.3.0+)
- TASK-073: Type-narrow PEQBand.kind to Literal
- TASK-074: Extract confidence thresholds into named constants
- TASK-075: _band_mask already parameterised (verified, no changes needed)
- TASK-076: Make FitObjective.weights injectable
- CLI/README UX cleanup: fit-offline alias, --max-filters help, --iteration-mode docs
- Archived 15 completed task specs to docs/tasks/archive/

## Recently completed (0.3.0)
- TASK-061: Confidence badge styling in GUI history view
- TASK-062: One-line confidence verdict in CLI fit output
- TASK-063: GUI setup diagnostics view (scrollable, refreshable)
- TASK-064: RBJ reference coefficient tests for biquad_response_db
- TASK-065: Biquad numerical stability tests for extreme parameters
- TASK-066: Graph display in GUI results view (xdg-open button)
- TASK-067: Multi-pass averaging iteration mode
- TASK-068: Fix dead mask in _metrics (band-limited to 80-12kHz)
- TASK-069: Fix alignment_peak_ratio for negative offsets
- TASK-070: Fix shelf Q/S inconsistency in CamillaDSP export
- TASK-071: Remove dead code (validate_stereo_audio, inverse_sweep)
- TASK-072: Smoke tests for plots.py, unit tests for signals.py

## Recently completed (0.2.3)
- TASK-054: Reject mono or duplicated-channel captures during analysis
- TASK-059: Extend duplicated-channel detection to multichannel captures
- TASK-060: Refactor TASK-054 tests to use pytest.raises

## Recently completed (0.2.2)
- TASK-057: Add fixed-band GraphicEQ fitting on top of the shared objective/residual layer
- TASK-058: Expand synthetic regression coverage around fitting/export edge cases

## Future follow-up candidates

1. Wiener regularisation in transfer function estimation (improves FR at frequency extremes)
2. Residual bandwidth estimation from raw (unsmoothed) residual in _peaking_candidate
3. Parameterise _band_mask frequency limits (currently hardcoded 80-8000 Hz)
4. Replace top-8 candidate alignment search with local-maxima search above threshold
5. Multi-pass joint PEQ refinement after greedy placement (Nelder-Mead or L-M)
6. Vectorise fractional_octave_smoothing and replace freqz with direct biquad eval
7. Add export formats beyond CamillaDSP and APO if users actually need them
8. Extract confidence thresholds into named constants
9. Type-narrow PEQBand.kind to Literal["peaking", "lowshelf", "highshelf"]
10. Make FitObjective.weights a method parameter for different use cases

## Future feature candidates (deferred)

1. Asynchronous Device Support and Clock Drift Compensation
2. Automated HRTF Target Integration and Scaling
3. Integration of CamillaDSP Live-Updates via WebSocket API
4. Closed-loop EQ refinement (depends on #3)
5. Windows/macOS support (platform-aware measure.py backends)
6. APO AutoEQ import (load existing presets as starting point)
7. Headphone database integration (community measurement databases as clone targets)
8. GUI target curve editor (drag-and-drop spline editor)
9. Room correction / speaker measurement mode
