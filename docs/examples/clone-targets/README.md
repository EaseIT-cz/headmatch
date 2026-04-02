# Clone target examples

These example CSVs show the intended `headmatch clone-target` workflow without trying to be a measurement database.

## Included examples

- `ananda_nano_published.csv` — source-shaped published curve example
- `hd800s_published.csv` — target-shaped published curve example
- `ananda_nano_to_hd800s_clone.csv` — prebuilt clone target generated from the two examples

## Typical workflow

Build your own clone target:

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

## Notes

- These are small, readable examples for docs and tests.
- Real published curves often have many more points; `headmatch` resamples them onto its own fitting grid.
- Clone targets are normalized at 1 kHz before diffing, so broad tonal balance matters more than absolute SPL offset.


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

### What to expect

Do **not** expect a perfect “turn headphone A into headphone B” result. These example clone targets are best treated as tonal starting points. Results may differ because of:

- your actual measured JT7/HD650 may not match the small published-curve example exactly
- clone targets are normalized at 1 kHz, so they capture tonal tilt more than absolute level differences
- HeadMatch uses conservative PEQ fitting, not unlimited correction
- fit quality still depends on the measurement itself, positioning repeatability, and the confidence score

### Practical interpretation

If the result is “not even near expected”, the most common causes are:
- the live measurement of the source headphone differs a lot from the published example source curve
- the target expectation is too literal; the clone target is meant to approximate tonal direction, not produce a perfect identity swap
- the run has warnings / low confidence and should not be trusted as-is

The right workflow is:
- use the clone target as a **starting point**
- inspect `fit_overview.svg` and the confidence summary
- adjust expectations or refine the target if you want a stronger or gentler version of that tonal move
