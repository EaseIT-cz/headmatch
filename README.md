# headmatch

A Python toolkit for:
- measuring headphone transfer functions on **Linux + PipeWire**
- fitting **CamillaDSP** EQ presets
- building **headphone cloning** targets from measurements or published CSV data
- repeating the loop until the residual is small enough
- supporting both **online / fully automated capture** and **offline recorder-first capture**

## What it does

1. renders a logarithmic sweep WAV
2. either records the in-ear response with `pw-record` **or** prepares an offline sweep package for Zoom/H2n
3. estimates left/right frequency response
4. fits a conservative PEQ set
5. exports a **CamillaDSP** YAML preset
6. can build a **clone target** such as `Ananda Nano -> HD800S`
7. can iterate the whole process multiple times when capture is online

## Recommended Linux stack

- PipeWire (`pw-play`, `pw-record`, `wpctl status`)
- Python 3.10+
- CamillaDSP
- Roland CS-10EM or another in-ear/binaural mic system
- Zoom H2n if you want USB-interface mode or SD-card fallback

## Hardware notes

The Roland **CS-10EM** microphone section needs **2 V to 10 V plug-in power**. The Zoom **H2n** can act as a USB audio interface and its official manual says USB audio mode supports **44.1/48 kHz at 16-bit**. The H2n product page also says it can act as a **4-in/2-out audio interface**, and for clean measurements you should use the **external mic input**, enable plug-in power, and disable processing. citeturn354437search1turn354437search0turn354437search4

## Install

```bash
cd headmatch
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For testing, install the test dependencies:

```bash
pip install -r requirements-test.txt
```

## CLI overview

The easiest first run is:

```bash
headmatch start --out-dir out/session_01
```

That guided path runs one online measurement pass and exports CamillaDSP EQ files.

If you want the older explicit workflow, the lower-level commands are still available:

```bash
headmatch render-sweep
headmatch measure
headmatch prepare-offline
headmatch analyze
headmatch fit
headmatch fit-offline
headmatch clone-target
headmatch iterate
```

## Online workflow: fully automated with PipeWire

This is the preferred path when the H2n behaves as a USB interface.

### 1) Put the H2n in USB audio-interface mode

Set the H2n to USB audio mode, 48 kHz if possible, external mic input, manual gain, and disable AGC/limiter/low-cut. The generated defaults also use 48 kHz. citeturn354437search0turn354437search4

### 2) Find the PipeWire nodes

```bash
wpctl status
```

PipeWire's own docs use `pw-play` for playback testing and `pw-loopback` for creating loopback nodes; this is the same ecosystem these scripts use. citeturn354437search10turn354437search6

### 3) Make one online measurement

```bash
headmatch measure   --out-dir out/measure_usb_01   --output-target "your-headphone-output-node"   --input-target "your-h2n-input-node"   --sample-rate 48000
```

This creates:
- `out/measure_usb_01/sweep.wav`
- `out/measure_usb_01/recording.wav`

### 4) Fit EQ

```bash
headmatch fit   --recording out/measure_usb_01/recording.wav   --out-dir out/fit_usb_01   --target-csv my_target.csv   --max-filters 8   --sample-rate 48000
```

Outputs:
- `camilladsp_full.yaml`
- `camilladsp_filters_only.yaml`
- `fit_report.json`
- measurement CSVs

### 5) Iterate automatically

```bash
headmatch iterate   --out-dir out/iterative_usb   --target-csv my_target.csv   --output-target "your-headphone-output-node"   --input-target "your-h2n-input-node"   --iterations 3   --max-filters 8   --sample-rate 48000
```

Each iteration gets its own folder.

## Offline workflow: record first, analyze later

Use this when:
- the H2n USB interface is flaky on Linux
- you want a stable SD-card workflow
- you want to compare multiple recordings manually

### 1) Prepare the sweep package

```bash
headmatch prepare-offline   --out-dir out/offline_session_01   --sample-rate 48000   --notes "Ananda Nano stock pads, no EQ"
```

This creates:
- `out/offline_session_01/sweep.wav`
- `out/offline_session_01/measurement_plan.json`

Copy `sweep.wav` to your playback machine if needed.

### 2) Record on the H2n

Record the response to SD card or via any other recorder path. Keep the file as stereo PCM WAV. Do **not** trim the leading silence manually.

### 3) Import the recording

Copy the recorded WAV to the session folder, for example:

```bash
cp /media/$USER/H2N/STE-0001.WAV out/offline_session_01/recording.wav
```

### 4) Analyze or fit directly

Analyze only:

```bash
headmatch analyze   --recording out/offline_session_01/recording.wav   --out-dir out/offline_session_01/analysis   --sample-rate 48000
```

Or fit in one step:

```bash
headmatch fit-offline   --recording out/offline_session_01/recording.wav   --out-dir out/offline_session_01/fit   --target-csv my_target.csv   --max-filters 8   --sample-rate 48000
```

### 5) Offline validation loop

Offline iteration is manual by design:
1. fit preset from recording A
2. load preset into CamillaDSP
3. record validation pass B on the H2n
4. run `fit-offline` or `analyze` on pass B
5. compare residuals in `fit_report.json`
6. repeat only if needed

That gives you the same math as online mode, just without automatic recapture.

## Headphone cloning

There are three ways.

### Option A: clone from your own measurements

Measure headphone A, measure headphone B, then create the difference curve:

```bash
headmatch clone-target   --source-csv out/ananda/measurement_left.csv   --target-csv out/hd800s/measurement_left.csv   --out out/ananda_to_hd800s_left.csv
```

Then fit headphone A to that curve.

### Option B: clone from published data

Use any CSV with frequency + response data. This includes:
- your own exported measurement CSVs
- AutoEq-style CSVs if they include frequency and raw response columns
- other measurement databases converted to CSV

Safety notes:
- keep `--out` pointed at a new file; `clone-target` now refuses to overwrite either input CSV
- both source and target curves must span **1 kHz**, because clone targets are normalized there before diffing

Example:

```bash
headmatch clone-target   --source-csv data/ananda_nano.csv   --target-csv data/hd800s.csv   --out out/ananda_to_hd800s.csv
```

Then:

```bash
headmatch fit   --recording out/ananda_live/recording.wav   --out-dir out/ananda_clone_fit   --target-csv out/ananda_to_hd800s.csv
```

### Option C: mixed mode

This is usually the smartest path:
- use published data to define the broad clone target
- use your own live measurement of the source headphone for the actual fit

That way the preset tracks **your** coupling instead of blindly trusting a rig average.

## CamillaDSP use

CamillaDSP uses a YAML configuration file and supports biquad-based EQ blocks, which is exactly what the exporter generates. The official docs show `camilladsp /path/to/config.yml` as the basic run form. citeturn354437search3turn354437search7

The script exports two YAML files.

### `camilladsp_full.yaml`
A full config template. You still need to replace:
- `devices.capture.device`
- `devices.playback.device`

### `camilladsp_filters_only.yaml`
Just the filter block and pipeline. Use this if you already have a working CamillaDSP base config.

Typical run:

```bash
camilladsp -p 1234 -m -a 127.0.0.1 -c out/fit_usb_01/camilladsp_full.yaml
```

## Suggested H2n setups

### H2n online / automated
- H2n in USB audio mode
- CS-10EM plugged into external mic input
- plug-in power on
- manual gain
- no AGC / compressor / limiter / low cut
- Linux sees H2n as capture device

### H2n offline / robust fallback
- H2n records to SD card
- same mic/gain/processing rules
- copy WAV into the session folder later
- run `fit-offline`

## CSV format rules

The loader accepts:
- `frequency_hz,response_db`
- `frequency_hz,raw`
- `frequency,response_db`
- `freq`,`freq_hz`, or `Hz` style frequency headers
- response headers such as `raw`, `raw_db`, `target_db`, `fr`, `equalization`, `Amplitude (dB)`, `Magnitude (dB)`, `Level (dB)`, or `SPL`
- many AutoEq-like CSVs where the first frequency-like column and the first response-like column are used

The CSV reader also ignores leading `#` comment lines, sorts rows into ascending frequency order when needed, and rejects duplicate frequency rows so clone inputs fail safely instead of producing ambiguous targets.

Everything is normalized at **1 kHz** before diffing or fitting, so target and clone files should include a point below and above 1 kHz.

## Practical advice

- Use **multiple reseats**. Ear coupling changes a lot.
- Do **left and right separately** when you are diagnosing pad-seal or cup-balance problems.
- Keep the sweep amplitude conservative at first.
- Do not overfit tiny >10 kHz wiggles.
- For cloning, match the **broad shape**, not every microscopic notch.
- On H2n, always prefer raw/manual capture over convenience features.

## Suggested workflow for Ananda Nano -> HD800S

1. get published FR CSVs or make your own measurements for both
2. generate a clone target with `clone-target`
3. measure your actual Ananda Nano on your ears
4. fit that live measurement to the clone target
5. listen
6. validate once
7. iterate only if the residual is still clearly worth fixing

## Testing

A synthetic test is included. It simulates a headphone response, measures it, fits EQ, and checks that the residual drops.

```bash
pip install -r requirements-test.txt
pytest -q
```

GitHub Actions runs this test suite automatically on every pull request and on pushes to `main` via [`.github/workflows/pytest.yml`](/home/chaos/PycharmProjects/headmatch/.github/workflows/pytest.yml). To actually block merges when tests fail, mark the `Pytest` check as required in the repository branch protection rules for `main`.

## Limits

This toolkit is realistic for:
- tonal correction
- removing broad peaks like 3–4 kHz glare
- making one headphone broadly resemble another

It is **not** realistic for perfectly cloning staging, cup geometry, or driver behavior.
