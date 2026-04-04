"""Fetch published headphone FR curves from community databases.

Currently supports AutoEQ (GitHub-hosted CSV files).
Used by the clone-target workflow to allow cloning without owning the target headphone.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import List, Tuple
from urllib.request import urlopen
from urllib.error import URLError

import numpy as np


AUTOEQ_RAW_BASE = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results"


def _parse_autoeq_csv(text: str) -> Tuple[np.ndarray, np.ndarray]:
    """Parse an AutoEQ frequency response CSV (frequency,raw)."""
    reader = csv.reader(io.StringIO(text))
    freqs, values = [], []
    for row in reader:
        if not row or not row[0].strip():
            continue
        try:
            f = float(row[0])
            v = float(row[1])
            freqs.append(f)
            values.append(v)
        except (ValueError, IndexError):
            continue
    if not freqs:
        raise ValueError("No valid frequency/response data found in CSV")
    return np.array(freqs), np.array(values)


def search_headphone(query: str, database: str = "autoeq") -> List[str]:
    """Search for headphone names matching a query.

    This is a best-effort search — it cannot enumerate the full database
    without a local index. Returns a list of possible match paths.
    """
    # For now, return a formatted suggestion since AutoEQ doesn't have a search API
    normalized = query.strip().replace(" ", "%20")
    return [
        f"Try: https://github.com/jaakkopasanen/AutoEq — search for '{query}'",
        f"Once found, use the raw CSV URL with: headmatch fetch-curve --url <raw-csv-url> --out curve.csv",
    ]


def fetch_curve_from_url(url: str, out_path: str | Path) -> Path:
    """Download a frequency response CSV from a URL and save it locally."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(url, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except (URLError, OSError) as e:
        raise ConnectionError(f"Failed to fetch {url}: {e}") from e

    # Validate it's parseable
    freqs, values = _parse_autoeq_csv(text)
    if len(freqs) < 10:
        raise ValueError(f"Fetched CSV has only {len(freqs)} points — expected a frequency response")

    # Write in HeadMatch's standard format
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frequency_hz", "response_db"])
        for freq, val in zip(freqs, values):
            writer.writerow([float(freq), float(val)])

    return out_path
