# HeadMatch

HeadMatch is a beginner-friendly headphone measurement and EQ tool for Linux.

It helps you:
- measure headphone response with **PipeWire** or an offline recorder workflow
- fit a conservative **parametric EQ** toward a target curve
- export ready-to-use **CamillaDSP** configurations and **Equalizer APO** presets
- build **clone targets** from your own measurements or published CSV curves
- review runs with graphs, summaries, and confidence guidance

The design goal is simple: make headphone measurement usable for audio enthusiasts who do **not** want to fight the tooling.

---

## Product strategy

HeadMatch currently has three frontends, but they do not have equal product priority:

- **GUI** — primary experience for most users
- **CLI** — explicit and scriptable workflow, also the most stable troubleshooting surface
- **TUI** — backup option, mainly for offline processing or systems without a usable desktop

That means most future feature work should land in the **GUI and CLI first**. The TUI remains supported, but it is no longer a primary investment area.

---

## What HeadMatch supports

### 1. Online measurement
Use PipeWire playback and recording to run a guided measurement directly on Linux.

### 2. Offline measurement
Generate a sweep package, record it with an external recorder, then import the WAV and fit EQ later.

### 3. EQ fitting
Analyze the measured response and generate a conservative PEQ profile aimed at audible improvement without overfitting.

### 4. EQ export
Write both **Equalizer APO** preset files and **CamillaDSP** configs from the same fit result.

### 5. Headphone cloning
Create a target curve that moves one headphone toward the tonal balance of another.

### 6. Result interpretation
Each run can include a plain-language trust summary so users can tell whether the measurement looks believable.

---

## Interaction modes

### GUI
Best for most users.

```bash
headmatch-gui
```

If you want HeadMatch to appear in your Linux desktop launcher, copy the example desktop entry from `docs/examples/headmatch.desktop` into `~/.local/share/applications/` and point `Exec=` at your installed `headmatch-gui` path.

### CLI
Best for explicit control, scripting, and repeatable workflows.

```bash
headmatch --version
headmatch start --out-dir out/session_01
headmatch list-targets
```

### TUI
Supported as a backup option, mainly for offline processing and non-desktop setups.

```bash
headmatch tui
```

All three modes share the same saved config, run summaries, and output formats.

---

## Installation

### Recommended: install from PyPI

Create a small virtualenv and install the published package:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install headmatch
```

After that, the main entry points should be available:

```bash
headmatch --version
headmatch doctor
headmatch-gui
```

If you are not sure your local setup is ready yet, run:

```bash
headmatch doctor
```

It gives a small readiness check for the config file, PipeWire tools, and device discovery before your first measurement.

### Install from source (development)

If you are working from a checkout and want the editable developer install instead:

```bash
cd headmatch
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For tests:

```bash
python -m pip install -r requirements-test.txt
```

### Optional: add a Linux desktop launcher

For GUI-first setups, you can add HeadMatch to your desktop app menu without changing packaging:

1. Find the installed GUI entry point.
   - inside a normal virtualenv this is usually `$(pwd)/.venv/bin/headmatch-gui`
   - otherwise use `command -v headmatch-gui`
2. Copy `docs/examples/headmatch.desktop` to:
   ```bash
   mkdir -p ~/.local/share/applications
   cp docs/examples/headmatch.desktop ~/.local/share/applications/headmatch.desktop
   ```
3. Edit `~/.local/share/applications/headmatch.desktop` and replace `Exec=/ABSOLUTE/PATH/TO/headmatch-gui` with the real absolute path from step 1.
4. Optionally set a custom `Icon=` path if you want something more specific than the generic `audio-headphones` icon.

After that, HeadMatch should show up in most Linux desktop launchers and app menus.

---

## Recommended first run

If you are unsure whether your machine is ready for online measurement, start with:

```bash
headmatch doctor
```

If the doctor output looks good and PipeWire playback and recording are working, continue with:

```bash
headmatch list-targets
headmatch start --out-dir out/session_01
```

This will:
1. generate a sweep
2. run one measurement pass
3. analyze the recording
4. fit EQ toward the selected target
5. export Equalizer APO and CamillaDSP files
6. write a human-readable `README.txt`, machine-readable `run_summary.json`, and reviewable fit graphs

If `headmatch doctor` reports missing PipeWire tools or no usable devices, fix that first or use the recorder-first offline path instead.

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

HeadMatch stores shared defaults in one config file used by the GUI, CLI, and TUI.

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
headmatch-gui --config /path/to/config.json
headmatch-tui --config /path/to/config.json
```

An example config is included at:

```text
docs/examples/headmatch.config.json
```

---

## Main CLI commands

### Guided online path
```bash
headmatch doctor
headmatch list-targets
headmatch start --out-dir out/session_01
```

### Manual online measurement
```bash
headmatch measure \
  --out-dir out/measure_usb_01 \
  --output-target "alsa_output.usb-..." \
  --input-target "alsa_input.usb-..."
```

### Fit an existing recording
```bash
headmatch fit \
  --recording out/measure_usb_01/recording.wav \
  --out-dir out/fit_usb_01 \
  --target-csv my_target.csv \
  --max-filters 8 \
  --fill-policy up_to_n
```

`--max-filters` sets the number of EQ filters per channel. With `--fill-policy up_to_n` (the default), the fitter uses up to that many filters, stopping early if the residual error is small. With `--fill-policy exact_n`, exactly that many filters are placed.

### Offline package generation
```bash
headmatch prepare-offline --out-dir out/offline_session_01
```

### Offline fitting
```bash
headmatch fit \
  --recording out/offline_session_01/recording.wav \
  --out-dir out/offline_session_01/fit \
  --target-csv my_target.csv
```

`fit-offline` is still accepted as an alias for `fit` for backward compatibility, but there is no difference between them.

### Iterative online workflow
```bash
headmatch iterate \
  --out-dir out/iterative_usb \
  --target-csv my_target.csv \
  --output-target "your-playback-node" \
  --input-target "your-capture-node" \
  --iterations 3 \
  --iteration-mode average
```

`--iteration-mode average` measures N times, averages the frequency responses, and fits once. This reduces noise from head position variation and ambient sound. The default `--iteration-mode independent` fits each pass separately (useful for consistency checking).

### Quick setup check
```bash
headmatch doctor
```

Use this when install or device setup feels uncertain. It is the fastest way to confirm the config file, PipeWire tools, and basic device discovery are in place.

### Clone target generation
```bash
headmatch clone-target \
  --source-csv source.csv \
  --target-csv target.csv \
  --out clone_target.csv
```

Use this when you want to create a **difference target** that moves one headphone toward another.

Preferred personal workflow:
1. measure headphone **A** on your rig
2. measure headphone **B** on the **same rig**
3. choose matching response CSVs from those two runs
4. build a clone target from A -> B
5. fit a fresh measurement of headphone A against that clone target

For personal measurements, the CSVs to feed into `headmatch clone-target` are the run output response files:
- `measurement_left.csv`
- `measurement_right.csv`

Use the **same side from both runs**.
Examples:
- `A/measurement_left.csv` with `B/measurement_left.csv`
- `A/measurement_right.csv` with `B/measurement_right.csv`

Do **not** mix left from one headphone with right from the other unless that is deliberately what you measured.
The raw files (`measurement_left_raw.csv` / `measurement_right_raw.csv`) are not the preferred inputs for this workflow.

Concrete personal example:

```bash
# 1) Measure headphone A (the one you want to change)
headmatch measure \
  --out-dir out/hd650_measure \
  --output-target "your-playback-node" \
  --input-target "your-capture-node"

# 2) Measure headphone B (the tonal balance you want to imitate)
headmatch measure \
  --out-dir out/hd800s_measure \
  --output-target "your-playback-node" \
  --input-target "your-capture-node"

# 3) Build a difference target from A -> B using matching artifacts
headmatch clone-target \
  --source-csv out/hd650_measure/measurement_left.csv \
  --target-csv out/hd800s_measure/measurement_left.csv \
  --out out/clone_targets/hd650_to_hd800s_left.csv

# 4) Fit headphone A using the clone target
headmatch fit \
  --recording out/hd650_measure/recording.wav \
  --target-csv out/clone_targets/hd650_to_hd800s_left.csv \
  --out-dir out/hd650_to_hd800s_fit
```

This is different from the lightweight example workflow in `docs/examples/clone-targets/`: those shipped CSVs are small published-style examples for learning the command shape. They are useful for demos and experimentation, but the preferred path for serious personal cloning is to measure both headphones on your own rig and generate the difference target from those matching measurements.

---

## Output files

A typical fit output folder contains:
- `README.txt` — plain-language explanation of the run output
- `run_summary.json` — stable summary used by the GUI/TUI history views, including a confidence score, plain-language interpretation, and warnings
- `fit_report.json` — detailed fit report
- `measurement_left.csv`
- `measurement_right.csv`
- `equalizer_apo.txt`
- `equalizer_apo_graphiceq.txt`
- `camilladsp_full.yaml`
- `camilladsp_filters_only.yaml`
- `fit_overview.svg`
- `fit_left.svg`
- `fit_right.svg`

The general rule is:
- open `README.txt` if you want the human explanation
- open `run_summary.json` if you want the stable machine-readable summary, confidence score, and warnings
- use `equalizer_apo.txt` for Equalizer APO parametric filters, `equalizer_apo_graphiceq.txt` for Equalizer APO GraphicEQ, or one of the CamillaDSP YAML files for CamillaDSP

---

## Example target curves

General-purpose example target curves live in:

```text
docs/examples/targets/
```

Included example tonal targets:
- Harman-style
- diffuse-field
- free-field
- IEF neutral / Crinacle-style
- V-shape
- flat / studio

These are small, editable example targets for quick experimentation. They are intentionally lightweight starting points rather than claims of exact published reference datasets.

## Clone-target examples

Documented examples live in:

```text
docs/examples/clone-targets/
```

There are two distinct clone-target workflows:

### 1. Preferred personal workflow
Use this when you own or can measure both headphones on the same rig.

- measure the **source** headphone you want to change
- measure the **target** headphone whose tonal balance you want
- feed matching run artifacts into `headmatch clone-target`
- use the resulting difference target when fitting the source headphone

The important input files are the analyzed response CSVs written by HeadMatch:
- `measurement_left.csv`
- `measurement_right.csv`

Use matching sides from both runs. In practice that means either:
- left vs left, or
- right vs right

This personal-measurement path is the most trustworthy because the source and target curves come from the same coupler, mic chain, positioning style, and analysis pipeline.

### 2. Lightweight published-example workflow
Use this when you want to learn the command flow or try a rough tonal experiment from small example CSVs.

These examples are useful if you want to:
- understand the expected CSV shape
- see a simple published-curve clone workflow
- inspect a prebuilt example clone target
- try ready-to-use pairings such as:
  - FiiO JT7 → Ananda Nano
  - HD650 → HD800S

Important: the shipped clone-target CSVs are **difference targets**, not magic “make this headphone become that headphone” files.
Use them when measuring the matching **source** headphone, then review the graphs and confidence summary to see how close the result actually got.

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
- CamillaDSP or Equalizer APO for applying the generated EQ
- in-ear or binaural microphone setups
- optional external recorder workflows

If your USB audio path is unstable, use the offline recorder-first workflow. That is a supported path, not a hack.

---

## Project docs

Current project docs live in:
- `docs/architecture.md`
- `docs/backlog.md`
- `docs/examples/`
- `docs/product_pages.md` (placeholder)

---

## Standalone binaries

Prebuilt binaries are available on the [GitHub Releases](https://github.com/EaseIT-cz/headmatch/releases) page for:

- **Linux x64** — `headmatch-linux-x64`, `headmatch-gui-linux-x64`
- **macOS Apple Silicon (M1/M2/M3)** — `headmatch-macos-arm64`, `headmatch-gui-macos-arm64`

### macOS: bypass "app not signed" error

On macOS, unsigned binaries will be blocked by Gatekeeper. To bypass:

```bash
xattr -dr com.apple.quarantine /path/to/headmatch-macos-arm64
```

Run this once on the extracted binary or the containing folder. After that, the binary will launch normally.
