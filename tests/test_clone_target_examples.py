from __future__ import annotations

from pathlib import Path

import numpy as np

from headmatch.targets import clone_target_from_source_target, load_curve


def test_clone_target_example_csvs_load_cleanly():
    root = Path("docs/examples/clone-targets")
    for name in [
        "ananda_nano_published.csv",
        "hd800s_published.csv",
        "fiio_jt7_published.csv",
        "hd650_published.csv",
        "ananda_nano_to_hd800s_clone.csv",
        "fiio_jt7_to_ananda_nano_clone.csv",
        "hd650_to_hd800s_clone.csv",
    ]:
        curve = load_curve(root / name)
        assert len(curve.freqs_hz) >= 2
        assert curve.freqs_hz[0] <= 1000.0 <= curve.freqs_hz[-1]


def test_prebuilt_clone_targets_match_regenerated_examples(tmp_path):
    root = Path("docs/examples/clone-targets")
    cases = [
        (
            "ananda_nano_published.csv",
            "hd800s_published.csv",
            "ananda_nano_to_hd800s_clone.csv",
        ),
        (
            "fiio_jt7_published.csv",
            "ananda_nano_published.csv",
            "fiio_jt7_to_ananda_nano_clone.csv",
        ),
        (
            "hd650_published.csv",
            "hd800s_published.csv",
            "hd650_to_hd800s_clone.csv",
        ),
    ]

    for source_name, target_name, clone_name in cases:
        regenerated_path = tmp_path / clone_name
        clone_target_from_source_target(root / source_name, root / target_name, regenerated_path)
        regenerated = load_curve(regenerated_path)
        shipped = load_curve(root / clone_name)
        assert np.allclose(regenerated.freqs_hz, shipped.freqs_hz)
        assert np.allclose(regenerated.values_db, shipped.values_db)
