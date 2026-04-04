"""Tests for headphone database integration."""
from __future__ import annotations

from pathlib import Path
import numpy as np

from headmatch.headphone_db import _parse_autoeq_csv, search_headphone, fetch_curve_from_url


SAMPLE_CSV = """frequency,raw
20.0,-5.2
100.0,-2.1
1000.0,0.0
5000.0,3.5
10000.0,-1.0
15000.0,-4.2
"""


def test_parse_autoeq_csv():
    freqs, values = _parse_autoeq_csv(SAMPLE_CSV)
    assert len(freqs) == 6
    assert freqs[0] == 20.0
    assert values[2] == 0.0


def test_parse_autoeq_csv_skips_headers():
    text = "frequency,raw\n100,1.0\n200,2.0\n"
    freqs, values = _parse_autoeq_csv(text)
    assert len(freqs) == 2


def test_search_headphone_returns_suggestions():
    results = search_headphone("HD650")
    assert len(results) >= 1
    assert any("HD650" in r for r in results)


def test_parse_empty_csv_raises():
    import pytest
    with pytest.raises(ValueError, match="No valid"):
        _parse_autoeq_csv("just,headers\n")


def test_fetch_curve_rejects_http_url():
    import pytest
    with pytest.raises(ValueError, match="Only HTTPS"):
        fetch_curve_from_url("http://example.com/curve.csv", "/tmp/out.csv")


def test_fetch_curve_rejects_file_url():
    import pytest
    with pytest.raises(ValueError, match="Only HTTPS"):
        fetch_curve_from_url("file:///etc/passwd", "/tmp/out.csv")


def test_search_headphone_is_honest():
    results = search_headphone("HD650")
    assert any("not yet automated" in r for r in results)
