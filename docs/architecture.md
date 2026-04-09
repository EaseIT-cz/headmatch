# HeadMatch architecture

## Product shape

HeadMatch is a cross-platform headphone measurement and EQ tool built for non-technical audio enthusiasts.

It provides one shared measurement/fitting backend with three user-facing frontends:
- **GUI** as the primary product experience
- **CLI** for explicit, scriptable, and power-user workflows
- **TUI** as a maintenance-only backup path, mainly for offline processing and non-desktop environments

Supported platforms:
- **Linux** via PipeWire (primary, fully tested)
- **macOS** via PortAudio/CoreAudio (0.6.0, requires `pip install headmatch[portaudio]`)
- **Windows** via PortAudio (untested, expected to work with `sounddevice`)

The product direction is deliberately conservative:
- guided workflows over flexible-but-confusing ones
- safe defaults over maximum tweakability
- readable output folders over opaque internal artifacts
- conservative EQ over aggressive overfitting
- shared backend logic instead of per-frontend behavior drift

---

## Core workflow

The shared backend performs the same high-level pipeline regardless of frontend or platform:

1. generate a logarithmic sweep
2. either:
   - play/record via the active audio backend (PipeWire or PortAudio), or
   - export an offline sweep package for recorder-first use
3. align the recording to the reference sweep
4. estimate left/right frequency response
5. normalize at 1 kHz
6. smooth the curves
7. fit conservative PEQ bands
8. export Equalizer APO and CamillaDSP output
9. render shared measured-vs-target review graphs
10. write summary/report artifacts for later review

---

## Audio backend architecture

Audio I/O is abstracted behind a pluggable backend system:

### `audio_backend.py`
- `AudioBackend` protocol defining the contract for all backends
- `AudioDevice` dataclass for discovered devices
- `DeviceConfig`, `DeviceSelection`, `MeasurementPaths` shared types
- `get_audio_backend()` factory: selects backend based on `sys.platform`
  - Linux → `PipeWireBackend`
  - macOS/Windows → `PortAudioBackend`

### `backend_pipewire.py`
- PipeWire implementation of `AudioBackend`
- Device discovery via `pw-dump` JSON parsing
- Default device detection via `wpctl status` + `wpctl inspect`
- Play-and-record via `pw-play` / `pw-record` subprocesses
- PipeWire-specific doctor checks (tool availability + device count)
- **Bug fix (0.7.1)**: File handle leak in `play_and_record()` — stderr file now properly closed via `with` statement

### `backend_portaudio.py`
- PortAudio implementation via `sounddevice` library
- Device discovery via `sd.query_devices()`; duplex devices split into separate playback/capture entries
- Default device detection via `sd.default.device`
- Simultaneous play/record via `sd.playrec(blocking=True)`
- Device targets accept both numeric IDs and name substrings
- PortAudio-specific doctor checks (sounddevice availability + device count)

### `measure.py`
- Platform-agnostic measurement orchestration
- Sweep rendering, offline measurement package generation
- Doctor checks: config validation + backend-specific checks + saved target validation
- Backward-compatible API wrappers (`PipeWireTarget`, `PipeWireDeviceConfig`, etc. are aliases to the new types)

---

## Main modules

### `signals.py`
- sweep generation
- smoothing helpers
- frequency-grid helpers

### `analysis.py`
- recording alignment via local-maxima cross-correlation search
- Wiener-regularised frequency-response estimation
- measurement CSV export
- reliability diagnostics used by confidence scoring

### `targets.py`
- target loading
- target normalization
- clone-target generation

### `peq.py`
- PEQ band modeling (peaking, lowshelf, highshelf filters) with type-safe Literal kind
- conservative greedy fitting heuristics (edge-shelf detection, broad-band preference)
- joint Nelder-Mead refinement pass after greedy placement
- raw (unsmoothed) residual bandwidth estimation for narrower Q accuracy
- injectable FitObjective weights for use-case customisation
- filter-budget enforcement (up_to_n vs exact_n fill policies)
- fixed-band GraphicEQ profile fitting (geq_10_band, geq_31_band)

### `exporters.py`
- Equalizer APO preset export generation (parametric and GraphicEQ formats)
- CamillaDSP export generation (snippet and full YAML)
- shared export for both L/R channels from the same fit result

### `apo_import.py` / `apo_refine.py`
- Equalizer APO parametric preset parser
- per-channel and mono preset support
- re-optimisation of imported presets against fresh measurements via joint Nelder-Mead

### `headphone_db.py`
- real headphone database search via GitHub API (AutoEQ repository)
- local index cache with 24-hour TTL
- case-insensitive, space-insensitive model name matching
- AutoEQ CSV parser and format conversion
- HTTPS-only URL validation with 5 MB response cap; URLs percent-encoded for spaces
- **Bug fix (0.7.1)**: Empty search query now returns `[]` instead of entire database
- **Bug fix (0.7.1)**: Added frequency-range validation for downloaded FR curves (must span below and above 1 kHz)

### `target_editor.py`
- drag-point target curve editor model
- PCHIP interpolation on 48 PPO grid
- save/load from standard HeadMatch CSV

### `plots.py`
- dependency-free SVG review graph generation
- shared measured-vs-target fitted overlays

### `pipeline.py`
- measurement-to-fit orchestration
- iterative workflow support
- target curve resolution (relative vs absolute)

### `pipeline_confidence.py`
- confidence scoring algorithm and threshold constants
- trustworthiness summary generation
- warning and interpretation text
- **Note**: Magic numbers need documentation (TASK-113)

### `pipeline_artifacts.py`
- fit artifact writing (exports, graphs, README, summary JSON)
- run summary construction
- shared by single-fit and iterative paths

### `paths.py`
- platform-aware config and cache directory helpers
- Linux: XDG paths; macOS: ~/Library; Windows: %APPDATA%
- tempdir fallback if primary path is not writable

### `settings.py`
- shared config loading/saving with field alias support
- first-run defaults
- config auto-saved by GUI after each successful workflow

### `contracts.py`
- `FrontendConfig` with platform-neutral `output_target`/`input_target` properties
- config serialization uses new field names; loading accepts both old (`pipewire_*`) and new
- run summary, confidence, and error dataclasses
- **Bug fix (0.7.1)**: Removed invalid `output_target`/`input_target` properties from `RunFilterCounts` and `RunErrorSummary` (copy-paste error)
- **Bug fix (0.7.1)**: Deduplicated `WorkflowName` Literal type

### `history.py`
- shared run-summary discovery for GUI and TUI
- **New (0.7.1)**: `confidence_icon()` — returns ✓/⚠/✗ Unicode icons
- **New (0.7.1)**: `format_run_entry()` — structured per-run display
- **New (0.7.1)**: `format_comparison_table()` — clean side-by-side layout

### `cli.py`
- command-line entry points
- explicit workflow surface
- platform-neutral help text
- **Bug fix (0.7.1)**: Deduplicated set literals in command routing
- **New (0.7.1)**: `batch-fit` command — process multiple recordings from manifest
- **New (0.7.1)**: `batch-template` command — generate batch manifest template
- **New (0.7.1)**: `history` command — list recent run summaries
- **New (0.7.1)**: `compare-runs` command — side-by-side comparison of recent runs
- **New (0.7.1)**: `compare-ab` command — A/B comparison with preset export

### `batch.py` (NEW in 0.7.1)
- batch-fit workflow implementation
- processes multiple recording/target pairs from JSON manifest
- each entry gets own output directory with standard EQ exports
- consolidated `batch_summary.json` tracks results, confidence, errors
- failures don't abort batch
- paths resolved relative to manifest file

### `ab_compare.py` (NEW in 0.7.1)
- A/B comparison tool for comparing two EQ runs
- copies Equalizer APO and CamillaDSP presets with A_/B_ prefixes
- generates `comparison.json` with per-metric diffs
- prints human-readable comparison table with verdict
- handles close results (< 0.1 dB difference)

### `gui.py` (37 lines)
- re-exports from gui/shell.py and gui_views.py for backward compatibility

### `gui/shell.py` (~1,011 lines, transitional)
- primary desktop workflow shell and composition root
- currently still owns navigation, picker orchestration, and several workflow entry points
- **Note**: Needs decomposition (TASK-109)

### `gui/controllers.py`
- workflow controllers extracted from shell
- online measurement, offline workflow, clone target, APO import/refine
- 79% coverage

### `gui/services.py`
- file picker helpers
- background task orchestration
- 93% coverage
- **Bug fix (0.7.1)**: Removed spurious `pragma: no cover` from error handler

### `gui/views/` (transitional)
- target structure for per-view modules
- current intent is one module per view family plus shared form helpers
- ongoing refactor should move rendering out of the legacy compatibility module

### `gui/views/basic.py`
- Basic Mode UI
- 83% coverage
- **New (0.7.1)**: Dynamic help text below target mode selector
- **New (0.7.1)**: Orange 'No devices found' hint for empty comboboxes

### `gui/views/common.py`
- Shared view components
- 93% coverage

### `gui/views/_legacy.py` (transitional)
- currently still contains most renderers and shared view helpers
- should be reduced to a thin compatibility module or removed after per-view extraction
- 31% coverage — needs attention
- **New (0.7.1)**: Missing-device guidance section with troubleshooting steps

### `gui_views.py` (legacy compatibility layer, transitional)
- currently still contains most renderers and shared view helpers
- should be reduced to a thin compatibility module or removed after per-view extraction

### `tui.py`
- maintenance-mode terminal workflow
- backup path for offline/recovery use

---

## Interaction model

### GUI
The GUI is the primary product experience.
It should be the first choice for most users.

### CLI
The CLI is the explicit and scriptable layer.
It should remain fully usable and well-documented because it is also the most stable troubleshooting surface.

### TUI
The TUI remains supported, but it is no longer a primary product investment area.
Its role is:
- backup operation when no desktop environment is available
- offline processing / recovery workflows
- lightweight terminal access

All three frontends share:
- the same persisted config
- the same measurement pipeline
- the same output artifacts
- the same run-summary contract

---

## Configuration model

HeadMatch uses one shared config file for GUI, CLI, and TUI.

Default paths (platform-aware via `paths.py`):
- Linux: `$XDG_CONFIG_HOME/headmatch/config.json` or `~/.config/headmatch/config.json`
- macOS: `~/Library/Application Support/headmatch/config.json`
- Windows: `%APPDATA%/headmatch/config.json`

The config stores small, stable user preferences:
- output directory defaults
- audio device targets (`output_target` / `input_target`)
- preferred target CSV
- sweep/fit defaults

Field naming migration:
- Old: `pipewire_output_target` / `pipewire_input_target`
- New: `output_target` / `input_target`
- Both accepted on read; new names written on save
- GUI auto-saves after each run, naturally migrating old configs

Explicit CLI flags override saved config for the current run.

---

## Output contract

Each run produces outputs that are understandable without digging through code.

Important artifacts:
- `README.txt` — human-readable explanation of the output folder
- `run_summary.json` — stable machine-readable summary
- `fit_report.json` — detailed fit report
- confidence / trust summary fields
- Equalizer APO preset export
- CamillaDSP YAML exports
- measurement CSVs
- shared SVG review graphs

---

## Design decisions

### 1. Guided workflows over low-level complexity
The intended audience values successful completion more than flexibility.

### 2. One backend, multiple frontends
The frontends should orchestrate the same core logic, not reimplement it.

### 3. GUI-first product strategy
New product-facing improvements should generally land in the GUI and CLI first.

### 4. Offline mode is first-class
Recorder-first workflows are part of the product, not a fallback hack.

### 5. Conservative EQ is a feature
The goal is useful tonal correction, not maximally clever curve chasing.

### 6. Pluggable audio backends
Platform-specific audio I/O is behind a protocol. Adding a new platform means one new file implementing `AudioBackend`, not touching the pipeline.

### 7. Output clarity matters
Users should be able to open a folder and understand what happened.

### 8. Trust signals matter
Confidence scoring and plain-language interpretation are part of the product.

---

## Current state

Version 0.7.1 (post-review). 618 deterministic tests passing in ~8.5s.

**Code review baseline**: commit 3607fbd (591 tests)
**Post-review**: 12 patches applied, 27 new tests added

Review delivered:
- 6 bug fixes (contracts.py, cli.py, headphone_db.py, backend_pipewire.py, gui/services.py)
- 3 new features (batch-fit, history/compare-runs, A/B comparison)
- 3 UI/UX improvements (target guidance, missing-device guidance, confidence icons)

The shipped product includes:
- Cross-platform audio backend (PipeWire on Linux, PortAudio on macOS/Windows)
- Platform-aware config/cache paths
- Standalone binaries: Linux x64, macOS ARM64
- GUI with live-updating target editor, canvas drag-to-move, confidence badges
- Beginner-first CLI with single-line confidence verdict
- Real headphone database search with space-insensitive matching
- APO import with Nelder-Mead refine mode
- Equalizer APO (parametric + GraphicEQ) and CamillaDSP export
- EQ clipping prediction with preamp recommendations
- Clone-target headphone-to-headphone workflow
- Multi-pass averaging iteration mode
- SVG review graphs in fit output folders
- Batch-fit workflow for multi-recording processing
- History review and A/B comparison commands
- CI matrix across Python 3.10–3.13 with coverage reporting
- Config auto-save from GUI with field name migration

---

## Likely future work

See `docs/backlog.md` for prioritized task list.

### Next (from code review)

- **TASK-109: Decompose gui/shell.py** — At 1,011 lines, the main GUI file handles state management, rendering dispatch, event handling, and workflow coordination. Extract `GuiState` into its own module, break out Tkinter variable initialization.
- **TASK-110: Standardize error hierarchy** — Define `HeadMatchError` base class with `MeasurementError`, `ConfigError`, `NetworkError` subclasses. Replace inconsistent ValueError/RuntimeError/ConnectionError usage.
- **TASK-111: Add type checking CI** — Codebase uses type hints extensively but no mypy/pyright step. Would catch issues at development time.
- **TASK-112: Add coverage CI gate** — Remove remaining `pragma: no-cover` markers, add CI step that fails if coverage drops below threshold (e.g., 80%).
- **TASK-113: Document confidence scoring derivation** — `pipeline_confidence.py` uses magic numbers (ALIGNMENT_SCORE_WARN=0.85, etc.) without explaining derivation.
- **TASK-114: Security: URL validation** — `fetch_curve_from_url` accepts any HTTPS URL. Consider domain allowlisting.

### GUI Refactoring (ongoing)

- **TASK-106: Split gui_views.py into per-view modules**
- **TASK-107: Extract workflow controllers**
- **TASK-108: Centralize file-picking and background task helpers**

### Later

- **TASK-115: Async audio backend** — Replace `time.sleep()` synchronization with asyncio-based process management.
- macOS .app bundle (currently distributed as raw binary)
- Windows .exe binary via PyInstaller
- AppImage wrapper for Linux
- Additional export formats beyond APO and CamillaDSP
- CamillaDSP live-update integration via WebSocket API
- Closed-loop EQ refinement (measure → apply → re-measure)
- Room correction / speaker measurement mode
- Windows installer and testing
