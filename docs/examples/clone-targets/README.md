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
