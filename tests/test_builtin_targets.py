"""Tests for built-in tonal target curves (advanced-mode selection)."""
from __future__ import annotations

from headmatch.builtin_targets import (
    BUILTIN_TARGET_DEFS,
    SELECTABLE_TARGET_NAMES,
    label_to_name,
    materialize_builtin_target,
)
from headmatch.targets import load_curve


def test_selectable_excludes_flat():
    assert "flat" not in SELECTABLE_TARGET_NAMES
    assert {"harman", "free_field", "diffuse_field"} <= set(SELECTABLE_TARGET_NAMES)


def test_label_to_name_maps_back_and_flat_is_none():
    assert label_to_name("Harman") == "harman"
    assert label_to_name("Flat (default)") is None
    assert label_to_name("nonexistent") is None


def test_materialize_builtin_target_writes_loadable_csv(tmp_path):
    path = materialize_builtin_target("harman", tmp_path)
    assert path.exists()
    curve = load_curve(path)
    # Harman: bass lift, 1 kHz reference ~0.
    freqs = list(curve.freqs_hz)
    i20 = freqs.index(min(freqs, key=lambda f: abs(f - 20)))
    i1k = freqs.index(min(freqs, key=lambda f: abs(f - 1000)))
    assert curve.values_db[i20] > curve.values_db[i1k]


def test_all_builtins_materialize_and_load(tmp_path):
    for name in BUILTIN_TARGET_DEFS:
        curve = load_curve(materialize_builtin_target(name, tmp_path))
        assert len(curve.freqs_hz) == 12
