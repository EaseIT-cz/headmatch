from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from headmatch.io_utils import _normalize_column_name, load_fr_csv, save_json, save_fr_csv


def test_normalize_column_name_handles_spacing_and_punctuation():
    assert _normalize_column_name(" Frequency (Hz) ") == "frequency_hz"
    assert _normalize_column_name("Response dB") == "response_db"
    assert _normalize_column_name(None) == ""


def test_load_fr_csv_detects_hinted_response_column(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("Hz,Compensation Error\n100,1.0\n200,2.0\n", encoding="utf-8")

    freqs, vals = load_fr_csv(path)

    assert np.allclose(freqs, [100.0, 200.0])
    assert np.allclose(vals, [1.0, 2.0])


def test_load_fr_csv_reorders_unsorted_frequencies(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("frequency_hz,response_db\n200,2.0\n100,1.0\n", encoding="utf-8")

    freqs, vals = load_fr_csv(path)

    assert np.allclose(freqs, [100.0, 200.0])
    assert np.allclose(vals, [1.0, 2.0])


def test_load_fr_csv_rejects_duplicate_frequencies(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("frequency_hz,response_db\n100,1.0\n100,2.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate frequency"):
        load_fr_csv(path)


def test_load_fr_csv_rejects_non_positive_frequency(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("frequency_hz,response_db\n0,1.0\n100,2.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="non-positive frequencies"):
        load_fr_csv(path)


def test_save_helpers_create_parent_dirs(tmp_path):
    csv_path = tmp_path / "nested" / "curve.csv"
    json_path = tmp_path / "nested" / "meta" / "data.json"

    save_fr_csv(csv_path, np.array([100.0, 200.0]), np.array([1.0, 2.0]))
    save_json(json_path, {"ok": True})

    assert csv_path.exists()
    assert json_path.exists()
