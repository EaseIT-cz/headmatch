# HeadMatch

**Personalise your headphone sound — with or without a measurement microphone.**

HeadMatch helps you build a ready-to-load EQ for your headphones and apply it in
**Equalizer APO**, **EasyEffects**, or **CamillaDSP**. You can:

- **Tune by ear, no equipment** — take a built-in **hearing test** and get an EQ matched to
  your own hearing.
- **Measure your headphones** with a microphone (PipeWire, or an offline recorder) and fit
  an EQ toward a target curve (Harman, free-field, flat, …).
- **Clone another headphone's sound** by building a difference target between two measurements.
- **Review every run** with graphs, a plain-language confidence score, and clipping checks.

The goal: make headphone personalisation usable for enthusiasts who don't want to fight the tooling.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip headmatch

headmatch-gui          # graphical app (recommended)
# or, command line:
headmatch --version
headmatch doctor       # check your setup
```

No microphone? Jump straight to the **[Hearing test](#hearing-test-equipment-free-eq)** — it
only needs headphones.

---

## Which workflow should I use?

| You want to… | Use | Needs a mic? |
|---|---|---|
| Get an EQ matched to **your hearing**, no gear | **Hearing test** (`headmatch hearing-test`) | No |
| Correct your headphone toward a **target curve** | **Measurement + fit** (`headmatch start` / `fit`) | Yes |
| Make one headphone **sound like another** | **Clone target** (`headmatch clone-target`) | Yes (both headphones) |
| Just apply an EQ you already have | See **[Applying your EQ](#applying-your-eq)** | No |

---

## Hearing test (equipment-free EQ)

The hearing test plays pure tones and asks you to click **"I hear it"**. From your responses
it builds a personalised EQ — **no measurement microphone required**, so it works on any
machine that can play sound.

**Run it:**

- **GUI:** open **Hearing Test** (available in both Basic and Advanced mode), set a
  comfortable volume at the pre-check, then follow the prompts.
- **CLI:**
  ```bash
  headmatch hearing-test            # run the test and save your hearing profile
  headmatch hearing-fit --out-dir out/hearing_fit   # generate an EQ from the saved profile
  headmatch hearing-test --fit --out-dir out/hearing_fit   # do both in one go
  ```

In the GUI you can **reuse a saved profile** ("Use Saved Profile") to regenerate an EQ
without re-testing, and in **Advanced mode** layer a tonal **target curve** (Harman / free
field / diffuse field / custom CSV) on top of the hearing correction.

**How it works (and its limits):**

- Each ear is measured **independently** and referenced to your own 1 kHz, so the result is
  **calibration-invariant** — your volume knob doesn't decide the outcome — and captures real
  **left/right differences**.
- The test repeats only the frequencies that look deviant (**adaptive**, so a clean ear
  finishes fast), and **rejects measurement noise** rather than correcting it.
- It runs a **volume check** (you should *not* hear the faint tone) and an **L/R channel
  check** before starting.

> **This is a personalisation aid, not a clinical audiogram.** It's uncalibrated and measures
> your perceived response *through your headphones*. For near-normal hearing it will
> correctly produce little or no EQ. For a measured, headphone-specific correction, use the
> microphone workflow below.

---

## Microphone measurement & EQ fitting

Measure your headphone's actual response and fit a conservative parametric EQ toward a target.

**Online (PipeWire), guided:**
```bash
headmatch doctor                       # confirm PipeWire + devices
headmatch list-targets                 # find your playback/capture node names
headmatch start --out-dir out/session_01
```
`start` runs a sweep → records → analyses → fits → exports APO + CamillaDSP + graphs + a summary.

**Offline (external recorder):**
```bash
headmatch prepare-offline --out-dir out/session_01   # get a sweep package
# ...record the sweep with your recorder, save recording.wav...
headmatch fit --recording out/session_01/recording.wav --out-dir out/session_01/fit
```

**Iterative (average several passes to cut noise):**
```bash
headmatch iterate --out-dir out/iter --target-csv my_target.csv \
  --output-target "your-playback-node" --input-target "your-capture-node" \
  --iterations 3 --iteration-mode average
```

EQ aggressiveness is controlled by `--max-filters` (filters per channel) and `--fill-policy`
(`up_to_n`, the default, stops early when the residual is small; `exact_n` places exactly N).
Each fit predicts **clipping** and recommends a preamp if boosts are too aggressive
(`--show-clipping` for detail, `--json` for the structured assessment).

---

## Clone another headphone's sound

Build a **difference target** that moves headphone A toward the tonal balance of headphone B.

```bash
# Measure both headphones on the SAME rig, then:
headmatch clone-target \
  --source-csv out/A_measure/measurement_left.csv \
  --target-csv out/B_measure/measurement_left.csv \
  --out out/clone/A_to_B_left.csv
# Fit A against the clone target:
headmatch fit --recording out/A_measure/recording.wav \
  --target-csv out/clone/A_to_B_left.csv --out-dir out/A_to_B_fit
```

Use **matching sides** (left-vs-left or right-vs-right) and the analysed `measurement_*.csv`
files (not the `*_raw.csv`). Ready-made published-curve examples (e.g. HD650 → HD800S) live in
`docs/examples/clone-targets/` for learning the flow. A clone target can also serve as a
**mic-calibration baseline** on a binaural rig — see `docs/examples/clone-target-calibration.md`.

---

## Applying your EQ

Every fit writes presets for the common hosts — load whichever matches your setup:

- **Equalizer APO** — `equalizer_apo.txt` (parametric) or `equalizer_apo_graphiceq.txt` (GraphicEQ).
- **EasyEffects** — import the APO preset. GraphicEQ exports are **clip-safe** (pure-cut, max
  0 dB), so they won't clip; turn your system volume up slightly to compensate for the cut.
- **CamillaDSP** — `camilladsp_full.yaml` (full config template) or `camilladsp_filters_only.yaml`
  (to merge into an existing config).

---

## Output files

A fit output folder contains:

| File | What it is |
|---|---|
| `README.txt` | Plain-language explanation of the run |
| `run_summary.json` | Stable machine-readable summary: confidence score, warnings, predicted error |
| `fit_report.json` | Detailed fit / band list |
| `equalizer_apo.txt`, `equalizer_apo_graphiceq.txt` | Equalizer APO presets (parametric, GraphicEQ) |
| `camilladsp_full.yaml`, `camilladsp_filters_only.yaml` | CamillaDSP configs |
| `measurement_left.csv`, `measurement_right.csv` | Estimated per-channel response (measurement fits) |
| `fit_overview.svg`, `fit_left.svg`, `fit_right.svg` | Review graphs (measurement fits) |
| `hearing_profile.json` | Your raw hearing thresholds (hearing fits) |

Hearing-test runs and measurement runs both write `run_summary.json`, so both appear in the
GUI's **Results** view and can be A/B compared.

---

## Interaction modes

All three share the same config, run summaries, and output formats. The GUI and CLI are the
primary, actively-developed surfaces.

- **GUI** (`headmatch-gui`) — recommended. **Basic** mode is a guided wizard; **Advanced** mode
  exposes devices, iterations, filter limits, and target selection.
- **CLI** (`headmatch …`) — explicit, scriptable, and the most stable troubleshooting surface.
- **TUI** (`headmatch tui`) — backup option for offline processing or non-desktop systems.

---

## Installation

### From PyPI (recommended)
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip headmatch
headmatch doctor      # readiness check
```

### From source (development)
```bash
cd headmatch
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-test.txt   # for tests
```

### Standalone binaries
Prebuilt binaries are on the [GitHub Releases](https://github.com/EaseIT-cz/headmatch/releases) page:

- **Linux x64** — `headmatch-linux-x64`, `headmatch-gui-linux-x64`
- **macOS Apple Silicon** — `headmatch-macos-arm64`, `headmatch-gui-macos-arm64`

On macOS, clear the Gatekeeper quarantine once:
```bash
xattr -dr com.apple.quarantine /path/to/headmatch-macos-arm64
```

### Optional: desktop launcher (Linux)
Copy `docs/examples/headmatch.desktop` to `~/.local/share/applications/` and set its `Exec=`
to the absolute path of `headmatch-gui` (find it with `command -v headmatch-gui`).

---

## Configuration

Shared defaults live in one config file used by the GUI, CLI, and TUI:

- `$XDG_CONFIG_HOME/headmatch/config.json` (fallback `~/.config/headmatch/config.json`)

It stores the preferred output folder, PipeWire playback/capture targets, preferred target
CSV, and sweep/fit defaults. Override the path with `--config /path/to/config.json` on any
entry point. An example is at `docs/examples/headmatch.config.json`.

Your saved **hearing profile** lives separately at `hearing_profile.json` in that same config
directory (e.g. `~/Library/Application Support/headmatch/` on macOS) and is reused across runs.

---

## Target curves

Editable example tonal targets are in `docs/examples/targets/`: Harman-style, diffuse-field,
free-field, IEF-neutral/Crinacle-style, V-shape, and flat/studio. They're lightweight starting
points, not claims of exact reference datasets. Pass one with `--target-csv`, or pick one in the
GUI's advanced target selector.

---

## Troubleshooting

```bash
headmatch doctor          # checks config, PipeWire tools, and device discovery
headmatch list-targets    # lists playback/capture node names for --output/--input-target
```

If your USB audio path is unstable, use the **offline recorder-first** workflow — it's a
supported path, not a workaround. For the hearing test, if it warns "volume too high," lower
your level until the faint tone in the pre-check is inaudible.

---

## Platform & environment

- **Linux + PipeWire** for microphone measurement (or an external recorder, offline).
- The **hearing test** needs only audio playback, so it works wherever HeadMatch runs.
- Apply the generated EQ with **Equalizer APO**, **EasyEffects**, or **CamillaDSP**.
- In-ear or binaural microphone setups recommended for measurement.

---

## Tests & docs

```bash
python -m pytest -q
```

Project docs: `docs/architecture.md`, `docs/designs/` (design notes, incl. the hearing-EQ
methodology), `docs/backlog.md`, `docs/examples/`.
