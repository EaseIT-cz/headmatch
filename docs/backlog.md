# HeadMatch backlog

## Current status

The current shipped state includes:
- beginner-first CLI workflow
- GUI shell, history browsing, and measurement wizard
- TUI backup workflow and history browsing (maintenance-only)
- shared settings persistence and preload
- improved capture/import robustness
- stronger alignment robustness coverage
- conservative PEQ/export polish
- clone examples and cross-source validation
- deterministic end-to-end synthetic integration tests
- GitHub Actions coverage for both main and integration test suites
- PipeWire device guidance
- measured-vs-target graph rendering
- Equalizer APO-compatible parametric and GraphicEQ preset export
- CamillaDSP export
- confidence / trust summaries in fit outputs
- fixed-band GraphicEQ fitting support (10-band and 31-band profiles)
- mono and duplicated-channel capture rejection (including multichannel files)

## Active — bugs (fix before next release)

1. TASK-068: Fix dead mask in _metrics (pipeline.py)
   `mask = (np.arange(len(err)) >= 0)` is always True. RMS error includes
   out-of-band noise, inflating confidence penalties.

2. TASK-069: Fix alignment_peak_ratio for negative offsets (analysis.py)
   Negative alignment offsets produce peak_ratio=0.0, incorrectly penalising
   confidence for early-arriving recordings.

3. TASK-070: Fix shelf Q/S inconsistency in CamillaDSP export
   Fitter stores RBJ slope S in band.q; CamillaDSP interprets it as Q.
   Export produces incorrect shelf filter parameters.

4. TASK-071: Remove dead code (validate_stereo_audio, inverse_sweep)
   Two orphaned functions that are never called.

5. TASK-072: Add smoke tests for plots.py and unit tests for signals.py
   Two modules with zero direct test coverage.

## Active — features and polish

6. TASK-061: Add confidence badge styling to GUI history view
7. TASK-062: Add one-line confidence verdict to CLI fit output
8. TASK-063: Add GUI setup diagnostics view
9. TASK-064: Add RBJ reference coefficient tests for biquad_response_db
10. TASK-065: Verify biquad numerical stability for extreme filter parameters
11. TASK-066: Display fit SVG graphs in the GUI results view
12. TASK-067: Add multi-pass averaging iteration mode

## Recently completed (0.2.3)
- TASK-054: Reject mono or duplicated-channel captures during analysis
- TASK-059: Extend duplicated-channel detection to multichannel captures
- TASK-060: Refactor TASK-054 tests to use pytest.raises

## Recently completed (0.2.2)
- TASK-057: Add fixed-band GraphicEQ fitting on top of the shared objective/residual layer
- TASK-058: Expand synthetic regression coverage around fitting/export edge cases

## Recently completed (earlier)
- TASK-056: Add Equalizer APO GraphicEQ export
- TASK-055: Add exact-count PEQ fitting mode
- TASK-053: Add GUI file and folder pickers for path fields
- surfaced confidence and interpretation more clearly in the GUI and CLI
- reduced duplicated fit artifact writing in pipeline.py
- split the GUI shell from view-rendering concerns
- strengthened typed confidence/run-summary contracts
- added conservative troubleshooting guidance tied to low-confidence results
- improved PipeWire target guidance in the CLI and GUI
- added a first GUI run-comparison slice in history
- added a first CLI environment diagnostics command (headmatch doctor)
- added GUI setup checks, target dropdowns, and navigation/layout cleanup
- expanded examples/docs for targets and clone-target workflows
- corrected clone-target backend semantics
- fixed PEQ filter-budget handling
- added package-build, release-asset, and PyPI publish GitHub Actions workflows
- updated docs so PyPI install is the primary user path

## Future follow-up candidates

1. Wiener regularisation in transfer function estimation (improves FR at frequency extremes)
2. Residual bandwidth estimation from raw (unsmoothed) residual in _peaking_candidate
3. Parameterise _band_mask frequency limits (currently hardcoded 80-8000 Hz)
4. Replace top-8 candidate alignment search with local-maxima search above threshold
5. Multi-pass joint PEQ refinement after greedy placement (Nelder-Mead or L-M)
6. Vectorise fractional_octave_smoothing and replace freqz with direct biquad eval
7. Add export formats beyond CamillaDSP and APO if users actually need them
8. Add more published curve examples if clone-target workflows generate repeated support questions
9. Consider a safe mode vs advanced mode split if the product accumulates too many knobs

## Future feature candidates (deferred)

1. Asynchronous Device Support and Clock Drift Compensation
2. Automated HRTF Target Integration and Scaling
3. Integration of CamillaDSP Live-Updates via WebSocket API
4. Closed-loop EQ refinement (measure → apply EQ → re-measure → correct residual; depends on #3)
5. Windows/macOS support (platform-aware measure.py backends)
6. APO AutoEQ import (load existing presets as starting point)
7. Headphone database integration (community measurement databases as clone targets)
8. GUI target curve editor (drag-and-drop spline editor)
9. Room correction / speaker measurement mode
