# Clone target examples

These example CSVs show the intended `headmatch clone-target` workflow without trying to be a measurement database.

## Two valid workflows

There are two different ways to use clone targets:

### 1. Preferred personal workflow

This is the recommended workflow when you can measure both headphones yourself on the same rig.

Goal:
- measure headphone **A**
- measure headphone **B**
- generate an **A -> B** difference target
- fit headphone **A** toward headphone **B**

This is the most reliable path because both curves come from the same coupler, mic chain, seating style, and HeadMatch analysis pipeline.

### 2. Lightweight published-example workflow

This is the smaller docs/demo workflow included in this folder.

Use it when you want to:
- understand the expected CSV shape
- learn the `headmatch clone-target` command
- inspect a prebuilt example clone target
- try a rough tonal experiment from small example curves

Treat these example CSVs as teaching material and tonal starting points, not as a substitute for measuring both headphones on your own rig.

## Included examples

- `ananda_nano_published.csv` — source-shaped published curve example
- `hd800s_published.csv` — target-shaped published curve example
- `ananda_nano_to_hd800s_clone.csv` — prebuilt clone target generated from the two examples

## Preferred personal workflow: from two measurements to one clone fit

### Step 1: Measure the source headphone

Measure the headphone you want to change.

```bash
headmatch measure \
  --out-dir out/hd650_measure \
  --output-target "your-playback-node" \
  --input-target "your-capture-node"
```

### Step 2: Measure the target headphone

Measure the headphone whose tonal balance you want to imitate, using the same rig and general setup.

```bash
headmatch measure \
  --out-dir out/hd800s_measure \
  --output-target "your-playback-node" \
  --input-target "your-capture-node"
```

### Step 3: Pick the correct CSV artifacts for `headmatch clone-target`

For this workflow, the intended inputs are the analyzed response CSVs written by HeadMatch:

- `measurement_left.csv`
- `measurement_right.csv`

Use the **same side from both runs**:
- source left with target left, or
- source right with target right

Examples:

```text
out/hd650_measure/measurement_left.csv
out/hd800s_measure/measurement_left.csv
```

or

```text
out/hd650_measure/measurement_right.csv
out/hd800s_measure/measurement_right.csv
```

Do **not** use mismatched sides unless you intentionally measured that way.

For the normal personal workflow, prefer the smoothed analyzed files above rather than:
- `measurement_left_raw.csv`
- `measurement_right_raw.csv`

### Step 4: Build the difference target

```bash
headmatch clone-target \
  --source-csv out/hd650_measure/measurement_left.csv \
  --target-csv out/hd800s_measure/measurement_left.csv \
  --out out/clone_targets/hd650_to_hd800s_left.csv
```

That output CSV is a **difference target**: it tells HeadMatch how to move the measured HD650 in the direction of the measured HD800S tonal balance.

### Step 5: Fit the source headphone using that clone target

```bash
headmatch fit \
  --recording out/hd650_measure/recording.wav \
  --target-csv out/clone_targets/hd650_to_hd800s_left.csv \
  --out-dir out/hd650_to_hd800s_fit
```

This gives you the normal fit outputs for headphone A, but the target is now the measured A -> B difference target you created.

If you want the cleanest comparison, you can also re-measure headphone A immediately before the fit run and use that fresh recording with the same generated clone target.

## Lightweight published-example workflow

Build your own clone target from the example published-style curves:

```bash
headmatch clone-target \
  --source-csv docs/examples/clone-targets/ananda_nano_published.csv \
  --target-csv docs/examples/clone-targets/hd800s_published.csv \
  --out out/ananda_nano_to_hd800s.csv
```

Then fit your live source-headphone measurement against that target:

```bash
headmatch fit \
  --recording out/ananda_live/recording.wav \
  --target-csv out/ananda_nano_to_hd800s.csv \
  --out-dir out/ananda_clone_fit
```

## How to actually use a clone target

A clone target CSV is **not** an absolute FR target for every headphone. It is a **difference curve** that says:

> take a measurement of the source headphone, then move it in the direction of the target headphone's tonal balance

So for example:
- `fiio_jt7_to_ananda_nano_clone.csv` should be used when you are measuring a **FiiO JT7** and want to push it toward an **Ananda Nano-like balance**
- `hd650_to_hd800s_clone.csv` should be used when you are measuring an **HD650** and want to push it toward an **HD800S-like balance**

### Correct usage pattern

1. Measure the **source headphone you actually own**
2. Pass the matching clone target CSV with `--target-csv`
3. Review the graphs, confidence summary, and result guide before trusting the preset

Example:

```bash
headmatch fit \
  --recording out/fiio_jt7_live/recording.wav \
  --target-csv docs/examples/clone-targets/fiio_jt7_to_ananda_nano_clone.csv \
  --out-dir out/fiio_jt7_to_ananda_nano_fit
```

## Notes

- These published examples are small, readable docs/test fixtures.
- Real published curves often have many more points; `headmatch` resamples them onto its own fitting grid.
- Clone targets are normalized at 1 kHz before diffing, so broad tonal balance matters more than absolute SPL offset.

## What to expect

Do **not** expect a perfect “turn headphone A into headphone B” result. Clone targets are best treated as tonal starting points. Results may differ because of:

- your actual measured source headphone may differ from the published example source curve
- your personal target measurement may vary with seat, seal, and rig repeatability
- clone targets are normalized at 1 kHz, so they capture tonal tilt more than absolute level differences
- HeadMatch uses conservative PEQ fitting, not unlimited correction
- fit quality still depends on the measurement itself, positioning repeatability, and the confidence score

## Practical interpretation

If the result is “not even near expected”, the most common causes are:
- the source measurement differs a lot from the curve used to build the clone target
- the target expectation is too literal; the clone target is meant to approximate tonal direction, not produce a perfect identity swap
- the run has warnings / low confidence and should not be trusted as-is

The right workflow is:
- use the clone target as a **starting point**
- inspect `fit_overview.svg` and the confidence summary
- adjust expectations or refine the target if you want a stronger or gentler version of that tonal move
