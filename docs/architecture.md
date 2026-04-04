# HeadMatch architecture

## Product shape

HeadMatch is a Linux-first headphone measurement and EQ tool built for non-technical audio enthusiasts.

It provides one shared measurement/fitting backend with three user-facing frontends:
- **GUI** as the primary product experience
- **CLI** for explicit, scriptable, and power-user workflows
- **TUI** as a maintenance-only backup path, mainly for offline processing and non-desktop environments

The product direction is deliberately conservative:
- guided workflows over flexible-but-confusing ones
- safe defaults over maximum tweakability
- readable output folders over opaque internal artifacts
- conservative EQ over aggressive overfitting
- shared backend logic instead of per-frontend behavior drift

---

## Core workflow

The shared backend performs the same high-level pipeline regardless of frontend:

1. generate a logarithmic sweep
2. either:
   - play/record it with PipeWire, or
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

## Main modules

### `signals.py`
- sweep generation
- smoothing helpers
- frequency-grid helpers

### `measure.py`
- sweep rendering
- PipeWire playback/recording coordination
- offline measurement package generation

### `analysis.py`
- recording alignment
- frequency-response estimation
- measurement CSV export
- reliability diagnostics used by confidence scoring

### `targets.py`
- target loading
- target normalization
- clone-target generation

### `peq.py`
- PEQ band modeling (peaking, lowshelf, highshelf filters)
- conservative fitting heuristics (edge-shelf detection, broad-band preference)
- filter-budget enforcement (up_to_n vs exact_n fill policies)
- fixed-band GraphicEQ profile fitting (geq_10_band, geq_31_band)

### `exporters.py`
- Equalizer APO preset export generation (parametric and GraphicEQ formats)
- CamillaDSP export generation (snippet and full YAML)
- shared export for both L/R channels from the same fit result

### `plots.py`
- dependency-free SVG review graph generation
- shared measured-vs-target fitted overlays

### `pipeline.py`
- measurement-to-fit orchestration
- iterative workflow support
- result-summary generation
- confidence/trust interpretation generation

### `settings.py`
- shared config loading/saving
- first-run defaults

### `history.py`
- shared run-summary discovery for GUI and TUI

### `cli.py`
- command-line entry points
- explicit workflow surface

### `gui.py`
- primary desktop workflow
- history browsing
- guided measurement flow

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

Default path:
- `$XDG_CONFIG_HOME/headmatch/config.json`
- fallback: `~/.config/headmatch/config.json`

The config stores small, stable user preferences such as:
- output directory defaults
- PipeWire playback target
- PipeWire capture target
- preferred target CSV
- sweep/fit defaults

Explicit CLI flags override saved config for the current run.
The GUI and TUI preload the same saved defaults.

---

## Output contract

Each run should produce outputs that are understandable without digging through code.

Important artifacts:
- `README.txt` — human-readable explanation of the output folder
- `run_summary.json` — stable machine-readable summary
- `fit_report.json` — detailed fit report
- confidence / trust summary fields
- Equalizer APO preset export
- CamillaDSP YAML exports
- measurement CSVs
- shared SVG review graphs

The GUI and TUI history views use `run_summary.json` plus `README.txt` as the stable review contract.

---

## Design decisions

### 1. Guided workflows over low-level complexity
The intended audience values successful completion more than flexibility.

### 2. One backend, multiple frontends
The frontends should orchestrate the same core logic, not reimplement it.

### 3. GUI-first product strategy
New product-facing improvements should generally land in the GUI and CLI first.
The TUI is maintained as a backup, not as a co-equal primary surface.

### 4. Offline mode is first-class
Recorder-first workflows are part of the product, not a fallback hack.

### 4a. Target semantics must stay explicit
HeadMatch has two distinct target concepts:
- **absolute targets**: the desired normalized response shape after EQ
- **relative transform / clone targets**: a tonal delta that should be applied to the measured source response

The backend must not treat those as interchangeable.
If a relative clone target is used, the pipeline must resolve it into an effective absolute per-run target before fitting, plotting, and reporting.

### 5. Conservative EQ is a feature
The goal is useful tonal correction, not maximally clever curve chasing.

### 5a. Filter family and fill policy must stay separate
HeadMatch treats these as orthogonal choices:
- **filter family / actuator model**
  - free-form PEQ (peaking, shelf filters)
  - fixed-band GraphicEQ (geq_10_band, geq_31_band profiles)
- **fill policy**
  - conservative `up_to_n`
  - exact-count `exact_n`

That separation keeps the current conservative PEQ mode intact while allowing an exact-count PEQ mode and fixed-band GraphicEQ mode without rewriting the objective/residual logic.

### 6. Output clarity matters
Users should be able to open a folder and understand what happened.

### 7. Trust signals matter
Users should not have to guess whether a run is believable.
Confidence scoring and plain-language interpretation are part of the product, not optional analytics.

---

## Current state

The shipped product now includes:
- beginner-first CLI workflow
- GUI shell, history browsing, and measurement wizard
- TUI backup workflow and history browsing
- shared config persistence and preload
- clone-target support
- Equalizer APO parametric and GraphicEQ preset export
- CamillaDSP export
- fixed-band GraphicEQ fitting (10-band and 31-band profiles)
- measured-vs-target SVG review graphs in fit output folders
- deterministic end-to-end synthetic integration tests
- confidence/trust summaries in fit outputs
- mono and duplicated-channel capture rejection

---

## Likely future work

If future work resumes, the most sensible candidates are:
- additional export formats beyond APO and CamillaDSP if there is real demand
- more real-world published-curve examples
- safe mode vs advanced mode split if the product accumulates too many knobs

---

## Refactor direction for the current phase

The codebase does not need a broad redesign, but two targeted refactors are now justified because they directly support the active product work.

### 1. Keep the pipeline contract stable, but reduce output-writing duplication

`pipeline.py` currently owns both the fitting logic and the repeated artifact-writing flow for single runs and iterative runs.

The intended direction is:
- keep one shared fit/output contract
- extract repeated artifact writing behind a small helper or result-writer layer
- avoid changing output filenames or summary schema unless explicitly planned

This is a maintainability refactor, not a product redesign.

### 2. Treat the GUI as a shell plus workflow views, not one growing class

`gui.py` currently combines:
- shell layout
- view rendering
- local form state
- background task orchestration
- history display
- completion/error presentation

Because the GUI is the primary product surface, future work should move toward:
- a thin app shell/controller
- smaller view-rendering helpers or components
- shared presentation helpers for confidence/result messaging where practical

The goal is to make GUI-first product polish easier without changing the backend workflow contract.

### 3. Strengthen typed frontend-facing summary contracts

Confidence and run-summary payloads now matter to the product experience, not just internal reporting.

The intended direction is:
- keep `run_summary.json` as the stable frontend contract
- introduce clearer typed structures for confidence and summary payloads
- make GUI/CLI/TUI presentation changes safer by reducing ad-hoc dict usage

This should remain lightweight: dataclasses or `TypedDict`-level structure is enough.
