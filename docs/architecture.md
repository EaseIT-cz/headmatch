# HeadMatch architecture

## Product shape

HeadMatch is a Linux-first headphone measurement and EQ tool built for non-technical audio enthusiasts.

It provides one shared measurement/fitting backend with three user-facing frontends:
- **CLI** for explicit and scriptable workflows
- **TUI** for guided terminal interaction
- **GUI** for a simple desktop workflow

The product direction is deliberately conservative:
- guided workflows over flexible-but-confusing ones
- safe defaults over maximum tweakability
- readable output folders over opaque internal artifacts
- conservative EQ over aggressive overfitting

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
8. export CamillaDSP output
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

### `targets.py`
- target loading
- target normalization
- clone-target generation

### `peq.py`
- PEQ band modeling
- conservative fitting heuristics

### `exporters.py`
- CamillaDSP export generation

### `plots.py`
- dependency-free SVG review graph generation
- shared measured-vs-target fitted overlays

### `pipeline.py`
- measurement-to-fit orchestration
- iterative workflow support
- result-summary generation

### `settings.py`
- shared config loading/saving
- first-run defaults

### `history.py`
- shared run-summary discovery for TUI and GUI

### `cli.py`
- command-line entry points

### `tui.py`
- guided terminal workflow
- history browsing

### `gui.py`
- guided desktop workflow
- history browsing

---

## Interaction model

### CLI
The CLI is the most explicit layer.
It exposes both:
- a beginner-first guided command (`start`)
- lower-level commands for manual control

### TUI
The TUI is a guided terminal layer.
It exists for users who want help without leaving the terminal.

### GUI
The GUI is the most approachable layer.
It is intended to surface the same shared workflows with the least friction.

All three frontends share:
- the same persisted config
- the same measurement pipeline
- the same output artifacts
- the same run-summary contract

---

## Configuration model

HeadMatch uses one shared config file for CLI, TUI, and GUI.

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

---

## Output contract

Each run should produce outputs that are understandable without digging through code.

Important artifacts:
- `README.txt` — human-readable explanation of the output folder
- `run_summary.json` — stable machine-readable summary
- `fit_report.json` — detailed fit report
- CamillaDSP YAML exports
- measurement CSVs
- shared SVG review graphs

The TUI and GUI history views use `run_summary.json` plus `README.txt` as the stable review contract.

---

## Design decisions

### 1. Guided workflows over low-level complexity
The intended audience values successful completion more than flexibility.

### 2. One backend, multiple frontends
The frontends should orchestrate the same core logic, not reimplement it.

### 3. Offline mode is first-class
Recorder-first workflows are part of the product, not a fallback hack.

### 4. Conservative EQ is a feature
The goal is useful tonal correction, not maximally clever curve chasing.

### 5. Output clarity matters
Users should be able to open a folder and understand what happened.

---

## Current state

The shipped product now includes:
- beginner-first CLI workflow
- TUI wizard and history browsing
- GUI shell, history browsing, and measurement wizard
- shared config persistence and preload
- clone-target support
- CamillaDSP export
- deterministic end-to-end synthetic integration tests
- measured-vs-target SVG review graphs in fit output folders

---

## Likely future work

If future work resumes, the most sensible candidates are:
- better PipeWire device discovery/help
- additional export formats if there is real demand
- more real-world published-curve examples
