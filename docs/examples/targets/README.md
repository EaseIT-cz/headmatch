# Example target curves

These CSVs are small, readable **example tonal targets** for HeadMatch.

They are intended to:
- show the expected target CSV shape
- give users a few common tonal starting points
- remain easy to inspect and edit by hand

They are **not** meant to be authoritative reproductions of proprietary or published target datasets.
Use them as practical examples and starting presets.

## Included examples

- `harman_example.csv`
- `diffuse_field_example.csv`
- `free_field_example.csv`
- `ief_neutral_crinacle_example.csv`
- `v_shape_example.csv`
- `flat_studio_example.csv`

## Notes

- HeadMatch normalizes target curves at 1 kHz during loading.
- These files deliberately use a small number of points; HeadMatch resamples them onto its internal fitting grid.
- If you want a stricter or more personal house curve, duplicate one of these files and edit the dB values to taste.
