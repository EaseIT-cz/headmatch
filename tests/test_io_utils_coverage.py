"""Coverage tests for io_utils.py missing lines.

Targets: 90, 95, 102, 117-120, 125-128, 131, 133, 135.
"""
from __future__ import annotations

import pytest

from headmatch.io_utils import load_fr_csv


# ── line 90: no rows after filtering comments/blanks ──

def test_load_fr_csv_no_rows(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("# just a comment\n\n   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="No rows found"):
        load_fr_csv(path)


# ── line 95: header present but no data rows ──

def test_load_fr_csv_header_only(tmp_path):
    path = tmp_path / "header.csv"
    path.write_text("frequency_hz,response_db\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No data rows found"):
        load_fr_csv(path)


# ── line 102: no recognizable frequency column ──

def test_load_fr_csv_no_frequency_column(tmp_path):
    path = tmp_path / "nofreq.csv"
    path.write_text("foo,response_db\n1,2\n3,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not find a frequency column"):
        load_fr_csv(path)


# ── lines 114-116: value column found via hint, not priority list ──

def test_load_fr_csv_value_column_via_hint(tmp_path):
    # 'left_response' normalizes to contain hint 'response' but isn't in priority list.
    path = tmp_path / "hint.csv"
    path.write_text("frequency_hz,left_response\n100,1.0\n1000,2.0\n", encoding="utf-8")
    freqs, vals = load_fr_csv(path)
    assert list(vals) == [1.0, 2.0]


# ── lines 117-118: fall back to first non-freq column when no hint ──

def test_load_fr_csv_value_column_fallback_first(tmp_path):
    path = tmp_path / "fallback.csv"
    path.write_text("frequency_hz,xyz\n100,1.0\n1000,2.0\n", encoding="utf-8")
    freqs, vals = load_fr_csv(path)
    assert list(vals) == [1.0, 2.0]


# ── lines 119-120: only a frequency column, nothing else ──

def test_load_fr_csv_no_value_column(tmp_path):
    path = tmp_path / "onlyfreq.csv"
    path.write_text("frequency_hz\n100\n1000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not find response column"):
        load_fr_csv(path)


# ── lines 125-126: KeyError path ──
# csv.DictReader always provides every fieldname as a key in each row (missing
# cells become None), so a KeyError on r[freq_key] / r[value_key] cannot arise
# from real CSV input. We force it by feeding rows that lack the resolved key,
# patching csv.DictReader so fieldnames are detected but rows omit the column.

def test_load_fr_csv_key_error(tmp_path, monkeypatch):
    import csv as _csv

    path = tmp_path / "keyerr.csv"
    path.write_text("frequency_hz,response_db\n100,1.0\n1000,2.0\n", encoding="utf-8")

    real_dictreader = _csv.DictReader

    class StubReader:
        def __init__(self, *args, **kwargs):
            self._inner = real_dictreader(*args, **kwargs)
            self.fieldnames = self._inner.fieldnames

        def __iter__(self):
            # Yield rows missing the value column -> KeyError on r[value_key].
            return iter([{"frequency_hz": "100"}, {"frequency_hz": "1000"}])

    monkeypatch.setattr("headmatch.io_utils.csv.DictReader", StubReader)
    with pytest.raises(ValueError, match="Missing expected column"):
        load_fr_csv(path)


# ── lines 127-128: ValueError path (non-numeric data) ──

def test_load_fr_csv_non_numeric(tmp_path):
    path = tmp_path / "nonnum.csv"
    path.write_text("frequency_hz,response_db\n100,abc\n1000,2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not parse numeric"):
        load_fr_csv(path)


# ── line 131: invalid shape ──
# freqs and vals are built from the same rows list, so they always share length
# and are 1-D for real input. We force a mismatch with a patched np.array.

def test_load_fr_csv_invalid_shape(tmp_path, monkeypatch):
    import numpy as _np

    path = tmp_path / "shape.csv"
    path.write_text("frequency_hz,response_db\n100,1.0\n1000,2.0\n", encoding="utf-8")

    real_array = _np.array
    calls = {"n": 0}

    def fake_array(seq, dtype=None):
        calls["n"] += 1
        # Return a longer array on the second call (the values array) to break the
        # len(freqs) == len(vals) invariant.
        if calls["n"] == 2:
            return real_array([1.0, 2.0, 3.0], dtype=dtype)
        return real_array(seq, dtype=dtype)

    monkeypatch.setattr("headmatch.io_utils.np.array", fake_array)
    with pytest.raises(ValueError, match="Invalid frequency-response data shape"):
        load_fr_csv(path)


# ── ragged/short row: a data row with fewer cells than the header leaves the
# value cell as None (csv.DictReader restval default), so float(None) must be
# reported as a ValueError, not propagate an uncaught TypeError. ──

def test_load_fr_csv_short_row(tmp_path):
    path = tmp_path / "ragged.csv"
    # second data row is missing the response_db cell
    path.write_text("frequency_hz,response_db\n100,1.0\n1000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not parse numeric"):
        load_fr_csv(path)


# ── line 133: fewer than two rows ──

def test_load_fr_csv_single_row(tmp_path):
    path = tmp_path / "one.csv"
    path.write_text("frequency_hz,response_db\n100,1.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least two frequency rows"):
        load_fr_csv(path)


# ── line 135: non-finite values ──

def test_load_fr_csv_non_finite(tmp_path):
    path = tmp_path / "inf.csv"
    path.write_text("frequency_hz,response_db\n100,1.0\n1000,inf\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_fr_csv(path)


# ── line 137: non-positive frequency ──

def test_load_fr_csv_non_positive_freq(tmp_path):
    path = tmp_path / "neg.csv"
    path.write_text("frequency_hz,response_db\n0,1.0\n1000,2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-positive frequencies"):
        load_fr_csv(path)
