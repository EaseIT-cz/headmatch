# HeadMatch Changelog

## 0.6.1

Final release. All rc2 changes plus:

### Platform fixes
- macOS test suite now passes with platform-specific skips for PipeWire tests.
- XDG config path test skipped on non-Linux platforms (XDG is Linux-only).
- PortAudio backend test skipped on macOS (requires hardware).

### Binary builds
- Linux x64 standalone binary with OpenBLAS ELF alignment fix (numpy<2, scipy<1.14).
- macOS ARM64 standalone binary with sounddevice bundled for PortAudio support.
- scipy.interpolate added to PyInstaller hiddenimports (fixes target editor crash).

### Documentation
- Product pages placeholder for headmatch.github.io.
- Standalone binaries section in README with macOS quarantine bypass.


## 0.6.1rc2

### EQ clipping prediction
- New `headmatch/eq_clipping.py` module with `EQClippingAssessment` dataclass.
- `assess_eq_clipping()` forecasts whether fitted EQ profile will cause digital clipping.
- Computes required preamp gain to prevent clipping (preamp = -max_positive_boost).
- Quality concern warnings for moderate (>6 dB) and severe (>12 dB) headroom loss.
- Integrated into `pipeline.fit_from_measurement()` — automatically included in fit report.
- 13 new tests in `tests/test_eq_clipping.py`.

### Other changes
- GitHub issue templates for bug reports and feature requests.
- MANIFEST.in updated for sdist completeness.
- Test count: 507 → 520 (+13).

## 0.6.1rc1

Initial release candidate for 0.6.1.

### PEQ fitting
- Conservative Nelder-Mead refinement for PEQ fitting (replaces discrete grid search).
- FilterBudget configuration for PEQ vs GraphicEQ, filter count, fill policy.
- Confidence scoring with plain-language interpretation.

### APO workflow
- APO refine mode: import parametric EQ preset → fit to measured response.
- Real-time preview in GUI with before/after curves.

### Export
- Equalizer APO export: parametric EQ and GraphicEQ formats.
- CamillaDSP export with configurable sample rate.

### Clone-target workflow
- Headphone-to-headphone EQ: measure source, load target curve, generate EQ for destination.
- `clone_target_from_source_target()` for automated target generation.

### Multi-pass averaging
- Iteration mode for multi-measurement averaging.
- Improved measurement reliability through statistical filtering.

### Architecture
- Pluggable audio backend: PipeWire (Linux), PortAudio (macOS), extensible to others.
- AudioBackend protocol with device discovery, play/record, health checks.
- Platform-aware paths (~/.config on Linux, ~/Library on macOS, %APPDATA% on Windows).

### GUI
- Device dropdowns with ID + label.
- Default output: ~/Documents/HeadMatch/session_01.
- Config auto-save after successful runs.
- Desktop shortcut button (Linux only).
- Target editor with canvas drag-to-move control points.

### Tests
- 507 deterministic tests.
- CI matrix: Python 3.10–3.13.

## 0.6.0

### macOS support
- PortAudio audio backend via `sounddevice`: device discovery, play/record, doctor checks.
- Platform-aware config/cache paths (~/Library on macOS, %APPDATA% on Windows).
- Install with `pip install headmatch[portaudio]`.

### Architecture
- AudioBackend protocol with pluggable backends (PipeWire, PortAudio).
- measure.py split into audio_backend.py + backend_pipewire.py + backend_portaudio.py.
- Backward-compatible API wrappers preserved.

### GUI
- Device dropdowns show ID + label.
- Default output directory: ~/Documents/HeadMatch/session_01.
- Config auto-saved after every successful run.
- Desktop shortcut button hidden on non-Linux.

### Config
- New field names: output_target / input_target (old names still accepted).
- Legacy out/session_01 default auto-replaced.

### Text
- GUI and CLI use platform-neutral audio terminology.

### Tests
- 436 → 507 deterministic tests (+71).

## 0.5.2

### Fixes
- Headphone search now matches model numbers without spaces ("HD650" finds "HD 650").
- Fetch curve URLs with spaces now percent-encoded (fixes "can't contain control characters" error).
- Fetch curve "Save to" field updates on every selection, not just the first.
- APO refine GUI crash: `self.config_path` → `self.state.config_path`.
- Target editor no longer resets all values to flat when adding a control point.
- Canvas drag-to-move works smoothly (events bound to canvas, not destroyed items).

### Improvements
- Target editor: live-updating sliders, real-time curve preview, no "Apply changes" button.
- Canvas drag-to-move with log-freq/dB coordinate mapping and yellow highlight during drag.
- Curve preview moved above control points table; scrollable table for >8 points.
- GUI view extraction: Import APO, Fetch Curve, History views moved to gui_views.py.
- `_PlotGeometry` class for bidirectional freq↔pixel, dB↔pixel coordinate mapping.

### Tests
- 436 → 447 deterministic tests (+11).


[152 more lines - unchanged from original]
## 0.5.1

### Features
- APO refine mode: `headmatch refine-apo --preset eq.txt --recording rec.wav --out-dir refined/` loads an existing Equalizer APO preset and re-optimises bands against a fresh measurement using joint Nelder-Mead refinement. Report includes before/after error comparison.
- GUI refine view: the Import APO screen now includes a "Refine against a measurement" section with recording WAV picker, optional target CSV, and output folder.
- CI coverage reporting: pytest-cov runs on main pushes with coverage.xml artifact upload.

### Performance
- Python 3.10–3.13 CI matrix (unit tests across all four, integration on bookends).

### Reliability
- PipeWire capture pipe hardening: pw-record stdout→DEVNULL, stderr persisted to `pw-record-stderr.log` for post-mortem diagnosis.

### Removed
- `fit-offline` CLI alias removed (was identical to `fit`, no reported usage).

### Tests
- 432 → 436 deterministic tests (+4 refine mode tests).

## 0.5.0

### Features

- Real headphone database search: `headmatch search-headphone "HD 650"` queries AutoEQ via GitHub API, returns matching models with copy-paste fetch commands. Results cached locally for 24 hours.
- GUI search: new search field in Fetch Curve view with listbox results; selecting a model populates the URL for one-click download.
- Live curve preview in target editor: Canvas widget renders the PCHIP-interpolated target curve in real time with log-frequency axis, dB grid, octave lines, and control point markers.

### Performance
- O(N) fractional-octave smoothing replaces O(N²) matrix approach. Default grid: identical output (<0.001 dB). Dense 10k-point curves: ~4ms instead of quadratic blowup.
- Alignment peak detection uses `scipy.signal.find_peaks` (C-backed) instead of Python loop.

### Architecture
- Explicit shelf parameter semantics: `PEQBand.slope` field distinguishes shelf slope S from peaking Q. Backward compatible — existing code that sets `q` for shelves still works.
- Pipeline split: `pipeline.py` (547→267 lines) extracted into `pipeline_confidence.py` and `pipeline_artifacts.py`. Public API unchanged.

### Fixes
- UTF-8 encoding specified on all file I/O (prevents locale-dependent failures on Windows).
- `fetch_curve_from_url` raises `ValueError` on non-UTF-8 downloads instead of `UnicodeDecodeError`.
- Cache directory falls back to temp dir when home is read-only.

### Packaging
- Added `pytest.ini` with `pythonpath` config (tests runnable without editable install).
- Added `MANIFEST.in` for complete sdist (LICENSE, docs, tests, changelog).
- Added `[tool.setuptools.packages.find]` to exclude `tests/` from wheel.

### Tests
- 401 → 432 deterministic tests (+31).
- New coverage: smoothing regression/scalability, shelf semantics, alignment robustness, headphone DB search/caching/fallback, curve preview rendering.

## 0.4.5

### Fixes
- Target editor `from_csv` now loads all points from small CSVs and intelligently downsamples dense grids to ~24 control points (was hardcoded to 8).

## 0.4.4

### Fixes
- Dense GraphicEQ export now writes the PEQ-fitted response instead of the raw correction target, reducing clipping risk. (Note: further GraphicEQ clipping investigation tracked in TASK-077.)

### Features
- Target editor: per-row "+" add button inserts points between neighbours instead of a single confusing "Add point" button.
- Target editor: "Load CSV" button to load existing target curves for editing.
- History view: "Browse…" button for the search folder.
- Desktop shortcut management: `headmatch create-shortcut` / `remove-shortcut` CLI commands, GUI toggle button in Setup Check, and `headmatch doctor` integration.

## 0.4.1

### Fixes
- `--iteration-mode` now passed through CLI to pipeline (was silently ignored).
- `import-apo` re-exports imported bands to APO + CamillaDSP formats (was ignoring them).
- Windows graph opener uses `os.startfile()` instead of `shell=True` (security fix).
- `fetch-curve` restricted to HTTPS-only with 5 MB response cap.
- Added `tests/__init__.py` for sdist test suite compatibility.
- Merged duplicate `fit`/`fit-offline` CLI branches.
- `search-headphone` now honestly states it is a placeholder.
- Config JSON parse errors produce user-friendly messages.
- `--iterations` and `--max-filters` reject negative/zero values.

### Features
- GUI: Target Editor, Import APO, Fetch Curve, and iteration mode views added (full CLI parity).

## 0.4.0

### Performance
- Vectorised fractional-octave smoothing (~50× faster).
- Direct biquad transfer function evaluation replacing `scipy.signal.freqz` (3-5× faster).

### Features
- APO AutoEQ preset import (`headmatch import-apo`).
- Community headphone database integration (`headmatch search-headphone`, `headmatch fetch-curve`).
- GUI target curve editor with PCHIP interpolation.

## 0.3.0

### DSP accuracy
- Wiener-regularised transfer function estimation (noise suppression at frequency extremes).
- Raw residual bandwidth estimation for narrower Q accuracy on presence-region features.
- Local-maxima alignment search replacing top-8 global sort (robust to room echoes).
- Joint Nelder-Mead PEQ refinement after greedy placement.

### Features
- Multi-pass averaging iteration mode (`--iteration-mode average`).
- CLI one-line colored confidence verdict.
- GUI confidence badges (✓/⚠/✗), graph display button, scrollable setup diagnostics.

### Code quality
- 241 RBJ biquad coefficient reference tests across dense parameter grid.
- Extreme parameter stability tests (all finite and bounded).
- Smoke tests for `plots.py`, unit tests for `signals.py`.
- Type-narrowed `PEQBand.kind` to `Literal`.
- Confidence scoring thresholds extracted to named constants.
- Injectable `FitObjective.weights`.

### Fixes
- `_metrics` dead mask (was always-true, inflating confidence penalties).
- `alignment_peak_ratio` returning 0.0 for negative offsets.
- Shelf Q/S inconsistency in CamillaDSP export.
- Removed dead code (`validate_stereo_audio`, `inverse_sweep`).

## 0.2.3

### Fixes
- Mono captures rejected with clear error message.
- Duplicated-channel captures detected and rejected (all channel counts).
- Tests refactored to use `pytest.raises`.

## 0.2.2

### Features
- Fixed-band GraphicEQ export (10-band and 31-band profiles).
- Fixed-band GraphicEQ fitting on shared objective/residual layer.
- Exact-count PEQ mode (`exact_n` fill policy).
- Expanded synthetic regression test coverage.

## 0.2.1

### Fixes
- Clone-target semantics corrected (relative targets resolved before fitting).
- PEQ filter-budget enforcement fixed.
- PEQ fitter no longer wastes search budget on rejected candidates.

## 0.2.0

Initial public release.
- Beginner-first CLI, GUI, and TUI workflows.
- PipeWire online measurement and offline recorder-first path.
- Conservative PEQ fitting with edge-shelf detection.
- Equalizer APO and CamillaDSP export.
- Clone-target headphone-to-headphone workflow.
- Confidence/trust summaries with plain-language interpretation.
- Measured-vs-target SVG review graphs.
