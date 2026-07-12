"""Coverage tests for headphone_db.py missing lines.

Targets: 32-33, 37, 98-99, 103, 133-137, 201, 227, 239-258.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import headmatch.headphone_db as hdb
from headmatch.exceptions import MeasurementError, NetworkError
from headmatch.headphone_db import (
    _cache_dir,
    _fetch_and_cache_index,
    _get_index,
    _index_cache_path,
    _parse_autoeq_csv,
    fetch_curve_from_url,
)

ALLOWED_CURVE_URL = "https://raw.githubusercontent.com/user/repo/main/curve.csv"
PUBLIC_ADDRINFO = [(0, 0, 0, "", ("185.199.108.133", 443))]


def _mock_resp(raw: bytes) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── lines 32-33, 37: _cache_dir / _index_cache_path delegate to paths ──

def test_cache_dir_delegates_to_paths(tmp_path):
    fake = tmp_path / "cache"
    fake.mkdir()
    with patch("headmatch.paths.cache_dir", return_value=fake):
        assert _cache_dir() == fake


def test_index_cache_path_uses_cache_dir(tmp_path):
    fake = tmp_path / "cache"
    fake.mkdir()
    with patch("headmatch.paths.cache_dir", return_value=fake):
        assert _index_cache_path() == fake / "autoeq_index.json"


# ── lines 98-99: _fetch_and_cache_index network failure ──

def test_fetch_index_connection_error():
    from urllib.error import URLError

    with patch("headmatch.headphone_db.urlopen", side_effect=URLError("down")):
        with pytest.raises(NetworkError, match="Failed to fetch AutoEQ index"):
            _fetch_and_cache_index()


# ── line 103: _fetch_and_cache_index empty tree raises MeasurementError ──

def test_fetch_index_empty_tree_raises():
    resp = _mock_resp(json.dumps({"tree": []}).encode("utf-8"))
    with patch("headmatch.headphone_db.urlopen", return_value=resp):
        with pytest.raises(MeasurementError, match="No headphone entries"):
            _fetch_and_cache_index()


# ── lines 105-112 (success) + 133-137: _get_index cache hit & refresh ──

def test_fetch_index_success_writes_cache(tmp_path):
    cache_file = tmp_path / "autoeq_index.json"
    tree = {
        "tree": [
            {"path": "results/oratory1990/over-ear/Model X/Model X.csv", "type": "blob"},
        ]
    }
    resp = _mock_resp(json.dumps(tree).encode("utf-8"))
    with patch("headmatch.headphone_db.urlopen", return_value=resp), patch(
        "headmatch.headphone_db._index_cache_path", return_value=cache_file
    ):
        entries = _fetch_and_cache_index()
    assert len(entries) == 1
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text())
    assert cached["count"] == 1


def test_get_index_returns_cached_when_present():
    sentinel = [{"name": "X", "source": "s", "form_factor": "f", "csv_path": "results/a/b/X/X.csv"}]
    with patch("headmatch.headphone_db._load_cached_index", return_value=sentinel):
        assert _get_index() is sentinel


def test_get_index_fetches_when_no_cache():
    fetched = [{"name": "Y", "source": "s", "form_factor": "f", "csv_path": "results/a/b/Y/Y.csv"}]
    with patch("headmatch.headphone_db._load_cached_index", return_value=None), patch(
        "headmatch.headphone_db._fetch_and_cache_index", return_value=fetched
    ):
        assert _get_index() == fetched


def test_get_index_force_refresh_skips_cache():
    fetched = [{"name": "Z", "source": "s", "form_factor": "f", "csv_path": "results/a/b/Z/Z.csv"}]
    with patch("headmatch.headphone_db._load_cached_index") as mock_cache, patch(
        "headmatch.headphone_db._fetch_and_cache_index", return_value=fetched
    ):
        result = _get_index(force_refresh=True)
    assert result == fetched
    mock_cache.assert_not_called()


# ── line 201: _parse_autoeq_csv skips blank rows ──

def test_parse_csv_skips_blank_rows():
    text = "\n100,0.5\n\n   \n1000,1.0\n"
    freqs, values = _parse_autoeq_csv(text)
    assert len(freqs) == 2


# ── fetch_curve_from_url: lines 227, 239-258 ──

def test_fetch_rejects_oversized_response(tmp_path):
    # Return more than MAX_RESPONSE_BYTES so the size check trips (line 227).
    big = b"x" * (hdb.MAX_RESPONSE_BYTES + 1)
    resp = _mock_resp(big)
    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", return_value=resp
    ):
        with pytest.raises(MeasurementError, match="exceeds"):
            fetch_curve_from_url(ALLOWED_CURVE_URL, tmp_path / "out.csv")


def test_fetch_connection_error(tmp_path):
    from urllib.error import URLError

    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", side_effect=URLError("nope")
    ):
        with pytest.raises(NetworkError, match="Failed to fetch"):
            fetch_curve_from_url(ALLOWED_CURVE_URL, tmp_path / "out.csv")


def test_fetch_too_few_points(tmp_path):
    # 5 valid points < 10 (line 238).
    rows = "\n".join(f"{f},0.0" for f in [20, 100, 1000, 5000, 20000])
    resp = _mock_resp(("frequency,raw\n" + rows + "\n").encode("utf-8"))
    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", return_value=resp
    ):
        with pytest.raises(MeasurementError, match="only .* points"):
            fetch_curve_from_url(ALLOWED_CURVE_URL, tmp_path / "out.csv")


def _curve_text(freqs):
    return "frequency,raw\n" + "\n".join(f"{f},0.0" for f in freqs) + "\n"


def test_fetch_max_below_1khz(tmp_path):
    # 12 points but max < 1000 Hz (lines 240-244).
    freqs = list(range(20, 20 + 12 * 10, 10))  # 20..130
    resp = _mock_resp(_curve_text(freqs).encode("utf-8"))
    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", return_value=resp
    ):
        with pytest.raises(MeasurementError, match="at least 1 kHz"):
            fetch_curve_from_url(ALLOWED_CURVE_URL, tmp_path / "out.csv")


def test_fetch_min_above_1khz(tmp_path):
    # 12 points all above 1000 Hz (lines 245-249).
    freqs = list(range(2000, 2000 + 12 * 100, 100))
    resp = _mock_resp(_curve_text(freqs).encode("utf-8"))
    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", return_value=resp
    ):
        with pytest.raises(MeasurementError, match="includes frequencies below 1 kHz"):
            fetch_curve_from_url(ALLOWED_CURVE_URL, tmp_path / "out.csv")


def test_fetch_writes_standard_format(tmp_path):
    # Valid full-range curve: writes file (lines 251-258).
    freqs = [20, 50, 100, 200, 500, 800, 1000, 2000, 5000, 10000, 15000, 20000]
    resp = _mock_resp(_curve_text(freqs).encode("utf-8"))
    out = tmp_path / "nested" / "out.csv"
    with patch("headmatch.headphone_db.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO), patch(
        "headmatch.headphone_db.urlopen", return_value=resp
    ):
        result = fetch_curve_from_url(ALLOWED_CURVE_URL, out)
    assert result == out
    assert out.exists()
    content = out.read_text()
    assert content.startswith("frequency_hz,response_db")
    assert "20.0" in content
