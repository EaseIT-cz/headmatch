# HeadMatch Changelog

## 0.7.0

### GUI / workflow
- Added GUI Basic Mode with a guided 3-step workflow.
- Added a Basic/Advanced mode selector with mode-specific navigation.
- Added a Basic Mode clone-target workflow for headphone cloning / rig-specific mic-coloration nulling.
- Basic target selection now hides irrelevant controls and supports explicit choice when multiple database measurements match.

### Refactoring
- Split GUI views into per-view modules under `headmatch/gui/views/`.
- Added shared GUI helper/service layers for picker and background-task orchestration.
- Continued decomposing the GUI into a more maintainable structure.

### EQ clipping
- GUI completion now surfaces clipping risk and preamp recommendations.
- CLI `fit` output now supports `--show-clipping` and `--json` clipping details.

### Documentation / release process
- Added clone-target mic calibration documentation.
- Updated architecture, backlog, and release notes for 0.7.0.
- Release validation now records test and coverage results.
- GitHub Actions now enforce a coverage floor to prevent silent drops below the current baseline.

### Validation
- 531 tests passed.
- Coverage: 75.53% total (`pytest --cov=headmatch`).

## 0.6.1


### Platform stability
- macOS test suite passes with platform-specific skips for PipeWire-only tests.
- XDG config path test skipped on non-Linux (XDG is Linux-specific).
- PortAudio backend test skipped on macOS (requires hardware).
- 520+ deterministic tests across platforms.

### Standalone binaries
- Linux x64 one-file PyInstaller executable.
- macOS ARM64 native build with sounddevice bundled.
- Intel macOS build removed (all modern Macs are ARM64).

### EQ clipping prediction
- `assess_eq_clipping()` forecasts digital clipping risk.
- Computes preamp gain to prevent clipping.
- Quality warnings for headroom loss.
- 13 new tests.

### Fixes
- OpenBLAS ELF alignment: numpy<2, scipy<1.14.
- Target editor crash: scipy.interpolate in hiddenimports.

## 0.6.0

### macOS support
- PortAudio audio backend via `sounddevice`.
- Platform-aware config/cache paths.
- Install with `pip install headmatch[portaudio]`.

### Architecture
- AudioBackend protocol with pluggable backends.
- measure.py split into backend_pipewire.py + backend_portaudio.py.

### GUI
- Device dropdowns show ID + label.
- Config auto-saved after every run.

### Tests
- 436 → 507 tests (+71).

## 0.5.2

### Fixes
- Headphone search matches without spaces ("HD650" finds "HD 650").
- Fetch curve URLs percent-encoded.
- Target editor canvas drag-to-move.

### Tests
- 436 → 447 tests (+11).

## 0.5.1

### Features
- APO refine mode: re-optimise presets against fresh measurement.
- CI coverage reporting.

### Tests
- 432 → 436 tests.

## 0.5.0

### Features
- Real headphone database search via AutoEQ GitHub API.
- Live curve preview in target editor.

### Performance
- O(N) fractional-octave smoothing.
- C-backed alignment peak detection.

### Tests
- 401 → 432 tests (+31).

## 0.4.5

- Target editor CSV loading for small files.

## 0.4.4

- Dense GraphicEQ export uses PEQ-fitted response.
- Desktop shortcut management.

## 0.4.1

### Fixes
- `--iteration-mode` passed through CLI.
- Windows security fix for graph opener.

### Features
- GUI parity with CLI.

## 0.4.0

### Performance
- Vectorised smoothing (~50× faster).
- Direct biquad evaluation (3-5× faster).

### Features
- APO preset import.
- Community headphone database.
- GUI target curve editor.

## 0.3.0

### DSP
- Wiener-regularised transfer function estimation.
- Joint Nelder-Mead PEQ refinement.

### Features
- Multi-pass averaging.
- Confidence verdicts and badges.

### Tests
- 241 RBJ biquad coefficient tests.

## 0.2.3

- Mono and duplicated-channel capture rejection.

## 0.2.2

- Fixed-band GraphicEQ export and fitting.

## 0.2.1

- Clone-target semantics fix.
- PEQ filter-budget enforcement.

## 0.2.0

Initial public release.
