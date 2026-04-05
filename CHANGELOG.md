# HeadMatch Changelog

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
