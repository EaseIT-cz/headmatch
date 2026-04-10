from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import URLError

import numpy as np
import pytest

from headmatch.headphone_db import HeadphoneEntry, _build_index_from_tree, _fetch_and_cache_index, _load_cached_index, _normalize_for_search, _parse_autoeq_csv, fetch_curve_from_url


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self, *_args, **_kwargs):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_headphone_entry_raw_csv_url_encodes_spaces():
    entry = HeadphoneEntry(name="HD 650", source="oratory1990", form_factor="over-ear", csv_path="results/oratory1990/over-ear/HD 650/HD 650.csv")
    assert "%20" in entry.raw_csv_url


def test_build_index_from_tree_deduplicates_by_model_and_source():
    tree = {
        "tree": [
            {"path": "results/oratory1990/over-ear/HD 650/HD 650.csv"},
            {"path": "results/oratory1990/over-ear/HD 650/GraphicEQ.csv"},
            {"path": "results/crinacle/over-ear/HD 650/HD 650.csv"},
            {"path": "docs/ignore.txt"},
        ]
    }
    entries = _build_index_from_tree(tree)
    assert len(entries) == 2
    assert {e["source"] for e in entries} == {"oratory1990", "crinacle"}


def test_load_cached_index_returns_none_for_bad_json(tmp_path, monkeypatch):
    cache = tmp_path / "autoeq_index.json"
    cache.write_text("not json", encoding="utf-8")
    monkeypatch.setattr("headmatch.headphone_db._index_cache_path", lambda: cache)
    assert _load_cached_index() is None


def test_fetch_and_cache_index_writes_cache(tmp_path, monkeypatch):
    payload = json.dumps({"tree": [{"path": "results/oratory1990/over-ear/HD 650/HD 650.csv"}] }).encode("utf-8")
    monkeypatch.setattr("headmatch.headphone_db.urlopen", lambda *a, **k: DummyResponse(payload))
    cache = tmp_path / "autoeq_index.json"
    monkeypatch.setattr("headmatch.headphone_db._index_cache_path", lambda: cache)

    entries = _fetch_and_cache_index()

    assert len(entries) == 1
    assert cache.exists()


def test_parse_autoeq_csv_skips_invalid_rows_and_parses_valid_values():
    freqs, vals = _parse_autoeq_csv("bad\n20,1\nfoo,2\n30,3\n")
    assert np.allclose(freqs, [20.0, 30.0])
    assert np.allclose(vals, [1.0, 3.0])


def test_fetch_curve_from_url_rejects_http(tmp_path):
    with pytest.raises(ValueError, match="Only HTTPS"):
        fetch_curve_from_url("http://example.com/a.csv", tmp_path / "a.csv")


def test_fetch_curve_from_url_wraps_network_errors(tmp_path, monkeypatch):
    def boom(*_a, **_k):
        raise URLError("offline")
    monkeypatch.setattr("headmatch.headphone_db.urlopen", boom)
    with pytest.raises(ConnectionError, match="Failed to fetch"):
        fetch_curve_from_url("https://example.com/a.csv", tmp_path / "a.csv", allowed_domains=frozenset(["example.com"]))


def test_fetch_curve_from_url_rejects_small_csv(tmp_path, monkeypatch):
    text = "\n".join(["freq,val", "20,1", "30,2"]).encode("utf-8")
    monkeypatch.setattr("headmatch.headphone_db.urlopen", lambda *a, **k: DummyResponse(text))
    with pytest.raises(ValueError, match="expected a frequency response"):
        fetch_curve_from_url("https://example.com/a.csv", tmp_path / "a.csv", allowed_domains=frozenset(["example.com"]))


def test_normalize_for_search_compacts_punctuation_and_case():
    assert _normalize_for_search("HD-650 / Special") == "hd 650   special"


from unittest.mock import patch
from headmatch.headphone_db import search_headphone

MOCK_INDEX = [
    {"name": "TestPhone", "source": "test", "form_factor": "over-ear",
     "csv_path": "results/test/over-ear/TestPhone/TestPhone.csv"},
]


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_empty_query_returns_nothing(mock_idx):
    """Empty or whitespace-only queries must not match every entry."""
    assert search_headphone("") == []
    assert search_headphone("   ") == []
    assert search_headphone("  \t  ") == []
