from __future__ import annotations

from pathlib import Path

from headmatch.targets import load_curve


EXAMPLE_TARGETS = [
    "harman_example.csv",
    "diffuse_field_example.csv",
    "free_field_example.csv",
    "ief_neutral_crinacle_example.csv",
    "v_shape_example.csv",
    "flat_studio_example.csv",
]


def test_example_target_csvs_load_cleanly():
    root = Path("docs/examples/targets")
    for name in EXAMPLE_TARGETS:
        curve = load_curve(root / name)
        assert curve.name == Path(name).stem
        assert len(curve.freqs_hz) >= 2
        assert curve.freqs_hz[0] <= 1000.0 <= curve.freqs_hz[-1]
