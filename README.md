# HeadMatch

HeadMatch is a beginner-friendly headphone measurement and EQ tool for Linux.

It helps you:
- measure headphone response with **PipeWire** or an offline recorder workflow
- fit a conservative **parametric EQ** toward a target curve
- export ready-to-use **CamillaDSP** configurations
- build **clone targets** from your own measurements or published CSV curves
- use the same core workflow from the **CLI**, **TUI**, or **GUI**

The design goal is simple: make headphone measurement usable for audio enthusiasts who do **not** want to fight the tooling.

---

## What HeadMatch supports

### 1. Online measurement
Use PipeWire playback and recording to run a guided measurement directly on Linux.

### 2. Offline measurement
Generate a sweep package, record it with an external recorder, then import the WAV and fit EQ later.

### 3. EQ fitting
Analyze the measured response and generate a conservative PEQ profile aimed at audible improvement without overfitting.

### 4. CamillaDSP export
Write both a full CamillaDSP config and a filters-only version.

### 5. Headphone cloning
Create a target curve that moves one headphone toward the tonal balance of another.

---

## Interaction modes

HeadMatch currently provides three ways to use the same shared pipeline.

### CLI
Best for explicit control, scripting, and repeatable workflows.

```bash
headmatch --version
headmatch start --out-dir out/session_01
```

### TUI
Best for a guided terminal workflow.

```bash
headmatch tui
```

### GUI
Best for users who want a simple desktop shell.

```bash
headmatch-gui
```

All three modes share the same saved config, run summaries, and output formats.

---

## Installation

```bash
cd headmatch
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For tests:

```bash
pip install -r requirements-test.txt
```

---

## Recommended first run

If PipeWire playback and recording are working, start here:

```bash
headmatch start --out-dir out/session_01
```

This will:
1. generate a sweep
2. run one measurement pass
3. analyze the recording
4. fit EQ toward the selected target
5. export CamillaDSP files
6. write a human-readable `README.txt` and machine-readable `run_summary.json`

If you prefer the recorder-first path:

```bash
headmatch prepare-offline --out-dir out/session_01
```

Then record the sweep externally and run:

```bash
headmatch fit-offline \
  --recording out/session_01/recording.wav \
  --out-dir out/session_01/fit
```

---

## Shared configuration

HeadMatch stores shared defaults in one config file used by the CLI, TUI, and GUI.

Default path:
- `$XDG_CONFIG_HOME/headmatch/config.json`
- fallback: `~/.config/headmatch/config.json`

That config can store things like:
- preferred output folder
- PipeWire playback target
- PipeWire capture target
- preferred target CSV
- sweep and fit defaults

You can override the path with:

```bash
headmatch --config /path/to/config.json ...
```

An example config is included at:

```text
docs/examples/headmatch.config.json
```

---

## Main CLI commands

### Guided online path
```bash
headmatch start --out-dir out/session_01
```

### Manual online measurement
```bash
headmatch measure \
  --out-dir out/measure_usb_01 \
  --output-target "your-playback-node" \
  --input-target "your-capture-node"
```

### Fit an existing recording
```bash
headmatch fit \
  --recording out/measure_usb_01/recording.wav \
  --out-dir out/fit_usb_01 \
  --target-csv my_target.csv \
  --max-filters 8
```

### Offline package generation
```bash
headmatch prepare-offline --out-dir out/offline_session_01
```

### Offline fitting
```bash
headmatch fit-offline \
  --recording out/offline_session_01/recording.wav \
  --out-dir out/offline_session_01/fit \
  --target-csv my_target.csv
```

### Iterative online workflow
```bash
headmatch iterate \
  --out-dir out/iterative_usb \
  --target-csv my_target.csv \
  --output-target "your-playback-node" \
  --input-target "your-capture-node" \
  --iterations 3
```

### Clone target generation
```bash
headmatch clone-target \
  --source-csv source.csv \
  --target-csv target.csv \
  --out clone_target.csv
```

---

## Output files

A typical fit output folder contains:
- `README.txt` — plain-language explanation of the run output
- `run_summary.json` — stable summary used by the TUI/GUI history views
- `fit_report.json` — detailed fit report
- `measurement_left.csv`
- `measurement_right.csv`
- `camilladsp_full.yaml`
- `camilladsp_filters_only.yaml`

The general rule is:
- open `README.txt` if you want the human explanation
- open `run_summary.json` if you want the stable machine-readable summary

---

## Clone-target examples

Documented examples live in:

```text
docs/examples/clone-targets/
```

These examples are useful if you want to:
- understand the expected CSV shape
- see a simple published-curve clone workflow
- inspect a prebuilt example clone target

---

## Test coverage

The repo includes:
- unit and functional tests
- deterministic synthetic integration tests for the CLI workflow
- GitHub Actions workflows for both the main test suite and integration tests

Run locally with:

```bash
python -m pytest -q
```

---

## Recommended hardware / environment

HeadMatch is currently designed around:
- Linux
- PipeWire
- CamillaDSP
- in-ear or binaural microphone setups
- optional external recorder workflows

If your USB audio path is unstable, use the offline recorder-first workflow. That is a supported path, not a hack.

---

## Project docs

Current project docs live in:
- `docs/architecture.md`
- `docs/backlog.md`
- `docs/examples/`

These are kept as the current source of truth for architecture, status, and examples.
