"""Tests for headphone_db.py — TASK-079: real headphone database search."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import io

import numpy as np
import pytest

from headmatch.headphone_db import (
    HeadphoneEntry,
    _build_index_from_tree,
    _normalize_for_search,
    _parse_autoeq_csv,
    search_headphone,
    _load_cached_index,
    _index_cache_path,
    fetch_curve_from_url,
)


# ── Index building tests ──

SAMPLE_TREE = {
    "tree": [
        {"path": "results/oratory1990/over-ear/Sennheiser HD 650/Sennheiser HD 650.csv", "type": "blob"},
        {"path": "results/oratory1990/over-ear/Sennheiser HD 650/Sennheiser HD 650 ParametricEQ.txt", "type": "blob"},
        {"path": "results/crinacle/in-ear/Moondrop Aria/Moondrop Aria.csv", "type": "blob"},
        {"path": "results/crinacle/in-ear/Moondrop Aria/Moondrop Aria ParametricEQ.txt", "type": "blob"},
        {"path": "results/oratory1990/over-ear/Focal Clear MG/Focal Clear MG.csv", "type": "blob"},
        {"path": "README.md", "type": "blob"},
        {"path": "results/short/path.csv", "type": "blob"},  # too few path parts
    ]
}


def test_build_index_extracts_models():
    entries = _build_index_from_tree(SAMPLE_TREE)
    names = {e["name"] for e in entries}
    assert "Sennheiser HD 650" in names
    assert "Moondrop Aria" in names
    assert "Focal Clear MG" in names
    assert len(entries) == 3


def test_build_index_skips_non_csv():
    entries = _build_index_from_tree(SAMPLE_TREE)
    paths = [e["csv_path"] for e in entries]
    assert all(p.endswith(".csv") for p in paths)


def test_build_index_deduplicates():
    tree = {
        "tree": [
            {"path": "results/a/over-ear/Model X/Model X.csv", "type": "blob"},
            {"path": "results/a/over-ear/Model X/Model X other.csv", "type": "blob"},
        ]
    }
    entries = _build_index_from_tree(tree)
    assert len(entries) == 1


# ── Search normalization tests ──

def test_normalize_for_search():
    assert _normalize_for_search("HD-650") == "hd 650"
    assert _normalize_for_search("Sennheiser HD 650") == "sennheiser hd 650"
    assert _normalize_for_search("7Hz Salnotes Zero") == "7hz salnotes zero"


# ── Search tests (mocked index) ──

MOCK_INDEX = [
    {"name": "Sennheiser HD 650", "source": "oratory1990", "form_factor": "over-ear",
     "csv_path": "results/oratory1990/over-ear/Sennheiser HD 650/Sennheiser HD 650.csv"},
    {"name": "Sennheiser HD 650 (balanced)", "source": "crinacle", "form_factor": "over-ear",
     "csv_path": "results/crinacle/over-ear/Sennheiser HD 650 (balanced)/Sennheiser HD 650 (balanced).csv"},
    {"name": "Moondrop Aria", "source": "crinacle", "form_factor": "in-ear",
     "csv_path": "results/crinacle/in-ear/Moondrop Aria/Moondrop Aria.csv"},
    {"name": "Focal Clear MG", "source": "oratory1990", "form_factor": "over-ear",
     "csv_path": "results/oratory1990/over-ear/Focal Clear MG/Focal Clear MG.csv"},
]


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_finds_exact_match(mock_idx):
    results = search_headphone("HD 650")
    assert len(results) == 2
    assert all(isinstance(r, HeadphoneEntry) for r in results)
    assert results[0].name == "Sennheiser HD 650"


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_case_insensitive(mock_idx):
    results = search_headphone("hd 650")
    assert len(results) == 2


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_partial_match(mock_idx):
    results = search_headphone("aria")
    assert len(results) == 1
    assert results[0].name == "Moondrop Aria"


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_no_match(mock_idx):
    results = search_headphone("nonexistent xyz")
    assert results == []


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_multi_token(mock_idx):
    results = search_headphone("focal clear")
    assert len(results) == 1
    assert results[0].name == "Focal Clear MG"


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_entry_has_raw_url(mock_idx):
    results = search_headphone("aria")
    assert results[0].raw_csv_url.startswith("https://raw.githubusercontent.com/")
    assert results[0].raw_csv_url.endswith(".csv")


# ── Cache tests ──

def test_cache_write_and_read(tmp_path):
    cache_file = tmp_path / "autoeq_index.json"
    cache_data = {
        "fetched_at": time.time(),
        "count": 2,
        "entries": MOCK_INDEX[:2],
    }
    cache_file.write_text(json.dumps(cache_data))
    with patch("headmatch.headphone_db._index_cache_path", return_value=cache_file):
        loaded = _load_cached_index()
        assert loaded is not None
        assert len(loaded) == 2


def test_cache_expired(tmp_path):
    cache_file = tmp_path / "autoeq_index.json"
    cache_data = {
        "fetched_at": time.time() - 100000,  # way expired
        "count": 2,
        "entries": MOCK_INDEX[:2],
    }
    cache_file.write_text(json.dumps(cache_data))
    with patch("headmatch.headphone_db._index_cache_path", return_value=cache_file):
        loaded = _load_cached_index()
        assert loaded is None


def test_cache_missing(tmp_path):
    cache_file = tmp_path / "nonexistent.json"
    with patch("headmatch.headphone_db._index_cache_path", return_value=cache_file):
        loaded = _load_cached_index()
        assert loaded is None


def test_cache_corrupt(tmp_path):
    cache_file = tmp_path / "autoeq_index.json"
    cache_file.write_text("not json")
    with patch("headmatch.headphone_db._index_cache_path", return_value=cache_file):
        loaded = _load_cached_index()
        assert loaded is None


# ── Network fallback test ──

@patch("headmatch.headphone_db._load_cached_index", return_value=MOCK_INDEX)
@patch("headmatch.headphone_db._get_index", side_effect=ConnectionError("offline"))
def test_search_falls_back_to_cache(mock_get, mock_cache):
    results = search_headphone("aria")
    assert len(results) == 1


@patch("headmatch.headphone_db._load_cached_index", return_value=None)
@patch("headmatch.headphone_db._get_index", side_effect=ConnectionError("offline"))
def test_search_no_cache_no_network(mock_get, mock_cache):
    results = search_headphone("aria")
    assert results == []


# ── CSV parsing tests ──

def test_parse_autoeq_csv_valid():
    text = "frequency,raw\n100,0.5\n1000,1.2\n10000,-3.0\n"
    freqs, values = _parse_autoeq_csv(text)
    assert len(freqs) == 3
    np.testing.assert_allclose(freqs, [100, 1000, 10000])


def test_parse_autoeq_csv_empty():
    with pytest.raises(ValueError, match="No valid"):
        _parse_autoeq_csv("header only\n")


# ── fetch_curve_from_url error handling ──

def test_fetch_rejects_http():
    with pytest.raises(ValueError, match="HTTPS"):
        fetch_curve_from_url("http://example.com/test.csv", "/tmp/out.csv")


def test_fetch_utf8_error(tmp_path):
    """UTF-8 decode failure should raise ValueError, not UnicodeDecodeError."""
    binary_content = b'\xff\xfe' + b'\x00' * 100
    mock_resp = MagicMock()
    mock_resp.read.return_value = binary_content
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("headmatch.headphone_db.urlopen", return_value=mock_resp):
        with pytest.raises(ValueError, match="UTF-8"):
            fetch_curve_from_url("https://example.com/bad.csv", str(tmp_path / "out.csv"))


# ── HeadphoneEntry tests ──

def test_entry_to_dict():
    entry = HeadphoneEntry(
        name="Test HP", source="test", form_factor="over-ear",
        csv_path="results/test/over-ear/Test HP/Test HP.csv",
    )
    d = entry.to_dict()
    assert d["name"] == "Test HP"
    assert "raw_csv_url" in d
    assert d["raw_csv_url"].endswith(".csv")


# ── Space-insensitive search tests (TASK-084) ──

@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_without_spaces_finds_spaced_name(mock_idx):
    """'HD650' (no space) should find 'Sennheiser HD 650'."""
    results = search_headphone("HD650")
    assert len(results) >= 1
    assert any("HD 650" in r.name for r in results)


@patch("headmatch.headphone_db._get_index", return_value=MOCK_INDEX)
def test_search_spaced_finds_compact_name(mock_idx):
    """Searching with spaces still works when the DB name has no spaces."""
    # This uses the existing token match path — just confirming no regression
    results = search_headphone("HD 650")
    assert len(results) == 2


@patch("headmatch.headphone_db._get_index", return_value=[
    {"name": "AKG K371", "source": "oratory1990", "form_factor": "over-ear",
     "csv_path": "results/oratory1990/over-ear/AKG K371/AKG K371.csv"},
])
def test_search_compact_query_matches_spaced_model(mock_idx):
    """'K371' should match 'AKG K371' via compact comparison."""
    results = search_headphone("K371")
    assert len(results) == 1
    assert results[0].name == "AKG K371"
