"""Fetch published headphone FR curves from community databases.

Currently supports AutoEQ (GitHub-hosted CSV files).
Used by the clone-target workflow to allow cloning without owning the target headphone.
"""
from __future__ import annotations

import csv
import ipaddress
import io
import json
import os
import socket
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote, urlparse

import numpy as np

from .exceptions import MeasurementError, NetworkError


# Allowed domains for URL validation (SSRF protection)
# - raw.githubusercontent.com: AutoEQ raw CSV data
# - api.github.com: GitHub API for repository index
ALLOWED_DOMAINS: tuple[str, ...] = (
    "raw.githubusercontent.com",
    "api.github.com",
)


def _is_private_ip(ip: str) -> bool:
    """Check if an IP address is private, loopback, or link-local.

    Returns True if the IP is:
    - Private (10.x.x.x, 172.16.x.x-172.31.x.x, 192.168.x.x)
    - Loopback (127.x.x.x)
    - Link-local (169.254.x.x)
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        # Invalid IP format
        return False


def _validate_url_for_ssrf(url: str) -> str:
    """Validate a URL to prevent SSRF (Server-Side Request Forgery) attacks.

    This function ensures that the URL:
    1. Uses the HTTPS scheme (rejects http, file, ftp, etc.)
    2. Points to an allowed domain
    3. Does not resolve to a private/internal IP address

    Args:
        url: The URL to validate.

    Returns:
        The validated URL unchanged.

    Raises:
        NetworkError: If the URL is invalid, not HTTPS, not in allowed domains,
                      or resolves to a private/internal IP.
    """
    parsed = urlparse(url)

    # Validate scheme is HTTPS
    if parsed.scheme != "https":
        raise NetworkError(f"scheme must be 'https' but got '{parsed.scheme}'")

    # Validate hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise NetworkError("URL must contain a valid hostname")

    # Validate hostname is in allowed domains (case-insensitive)
    if hostname.lower() not in (d.lower() for d in ALLOWED_DOMAINS):
        raise NetworkError(f"Domain '{hostname}' is not in the allowed list")

    # Validate that the hostname doesn't resolve to a private IP
    try:
        # Resolve hostname to IP address(es)
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        # DNS resolution failed
        raise NetworkError(f"Could not resolve hostname '{hostname}': {e}")

    for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
        ip_str = str(sockaddr[0])
        try:
            ipaddress.ip_address(ip_str)
        except ValueError:
            # Not an IP address, skip
            continue
        if _is_private_ip(ip_str):
            raise NetworkError(
                f"Domain '{hostname}' resolves to private IP: {ip_str}"
            )

    return url


AUTOEQ_RAW_BASE = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master"
AUTOEQ_TREE_API = "https://api.github.com/repos/jaakkopasanen/AutoEq/git/trees/master?recursive=1"

INDEX_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB cap
_USER_AGENT = "headmatch/0.4.6"


def _cache_dir() -> Path:
    """Return the headmatch cache directory, creating it if needed."""
    from .paths import cache_dir
    return cache_dir()


def _index_cache_path() -> Path:
    return _cache_dir() / "autoeq_index.json"


@dataclass
class HeadphoneEntry:
    """A single headphone model found in the AutoEQ database."""
    name: str
    source: str       # measurement source (e.g. "oratory1990", "crinacle")
    form_factor: str   # "in-ear", "over-ear", etc.
    csv_path: str      # relative path in the repo (results/source/type/Model/Model.csv)

    @property
    def raw_csv_url(self) -> str:
        """Direct raw.githubusercontent.com URL for the CSV."""
        encoded_path = quote(self.csv_path, safe="/")
        return f"{AUTOEQ_RAW_BASE}/{encoded_path}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d['raw_csv_url'] = self.raw_csv_url
        return d


def _build_index_from_tree(tree_data: dict) -> list[dict]:
    """Extract headphone entries from the GitHub tree API response."""
    entries = []
    seen = set()
    for item in tree_data.get("tree", []):
        path = item.get("path", "")
        if not path.startswith("results/") or not path.endswith(".csv"):
            continue
        parts = path.split("/")
        # Expected: results/Source/form-factor/Model/Model.csv
        if len(parts) < 5:
            continue
        source = parts[1]
        form_factor = parts[2]
        model = parts[3]
        # Deduplicate by (model, source)
        key = (model.lower(), source.lower())
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "name": model,
            "source": source,
            "form_factor": form_factor,
            "csv_path": path,
        })
    return entries


def _fetch_and_cache_index() -> list[dict]:
    """Fetch the AutoEQ repo tree from GitHub API and cache locally."""
    req = Request(AUTOEQ_TREE_API, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": _USER_AGENT,
    })
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read(50 * 1024 * 1024))  # GitHub tree can be large
    except (URLError, OSError) as e:
        raise NetworkError(f"Failed to fetch AutoEQ index from GitHub: {e}") from e

    entries = _build_index_from_tree(data)
    if not entries:
        raise MeasurementError("No headphone entries found in the AutoEQ tree (unexpected repo structure change?)")

    cache = {
        "fetched_at": time.time(),
        "count": len(entries),
        "entries": entries,
    }
    cache_path = _index_cache_path()
    cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return entries


def _load_cached_index() -> list[dict] | None:
    """Load the cached index if it exists and hasn't expired."""
    cache_path = _index_cache_path()
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = data.get("fetched_at", 0)
        if time.time() - fetched_at > INDEX_CACHE_TTL_SECONDS:
            return None
        entries = data.get("entries", [])
        return entries if entries else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _get_index(force_refresh: bool = False) -> list[dict]:
    """Get the headphone index, using cache when available."""
    if not force_refresh:
        cached = _load_cached_index()
        if cached is not None:
            return cached
    return _fetch_and_cache_index()


def _normalize_for_search(text: str) -> str:
    """Normalize text for fuzzy matching: lowercase, strip punctuation."""
    return "".join(c.lower() if c.isalnum() else " " for c in text).strip()


def search_headphone(query: str, database: str = "autoeq") -> list[HeadphoneEntry]:
    """Search the AutoEQ database for headphone models matching the query.

    Uses case-insensitive substring matching on the model name.
    Results are sorted by relevance (exact prefix match first, then alphabetical).
    Falls back to cached results if the API is unreachable.
    """
    # Try to get index, falling back to cache on network failure
    try:
        entries = _get_index()
    except NetworkError:
        cached = _load_cached_index()
        if cached is not None:
            entries = cached
        else:
            # No cache and no network — return empty with guidance
            return []

    query_norm = _normalize_for_search(query)
    if not query_norm:
        return []
    query_tokens = query_norm.split()

    matches = []
    query_compact = query_norm.replace(" ", "")

    for entry in entries:
        name_norm = _normalize_for_search(entry["name"])
        name_compact = name_norm.replace(" ", "")
        # All query tokens must appear in the name, OR the space-stripped
        # query appears in the space-stripped name (handles HD650 → HD 650)
        if all(token in name_norm for token in query_tokens) or query_compact in name_compact:
            matches.append(HeadphoneEntry(
                name=entry["name"],
                source=entry["source"],
                form_factor=entry["form_factor"],
                csv_path=entry["csv_path"],
            ))

    # Sort: exact prefix match first, then by name length (shorter = more specific), then alphabetical
    def sort_key(e: HeadphoneEntry) -> tuple:
        name_norm = _normalize_for_search(e.name)
        name_compact = name_norm.replace(" ", "")
        is_prefix = name_norm.startswith(query_norm) or name_compact.startswith(query_compact)
        return (not is_prefix, len(e.name), e.name.lower())

    matches.sort(key=sort_key)
    return matches


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
        raise MeasurementError("No valid frequency/response data found in CSV")
    return np.array(freqs), np.array(values)


def fetch_curve_from_url(url: str, out_path: str | Path) -> Path:
    """Download a frequency response CSV from a URL and save it locally.

    Security considerations:
    - Only HTTPS URLs are accepted (http, ftp, file, etc. are rejected)
    - URLs must point to allowed domains (raw.githubusercontent.com, api.github.com)
    - URLs are validated against SSRF attacks including private IP resolution

    Response size is capped at 5 MB.
    """
    # Validate URL for SSRF protection before any other processing
    _validate_url_for_ssrf(url)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(url, timeout=15) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise MeasurementError(f"Response exceeds {MAX_RESPONSE_BYTES // (1024*1024)} MB limit")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as e:
                raise MeasurementError("Downloaded file is not valid UTF-8 CSV text.") from e
    except (URLError, OSError) as e:
        raise NetworkError(f"Failed to fetch {url}: {e}") from e

    # Validate it's parseable and spans a usable frequency range
    freqs, values = _parse_autoeq_csv(text)
    if len(freqs) < 10:
        raise MeasurementError(f"Fetched CSV has only {len(freqs)} points — expected a frequency response")
    freq_min, freq_max = float(freqs[0]), float(freqs[-1])
    if freq_max < 1000.0:
        raise MeasurementError(
            f"Fetched CSV only covers up to {freq_max:.0f} Hz — "
            "expected a full-range frequency response reaching at least 1 kHz"
        )
    if freq_min > 1000.0:
        raise MeasurementError(
            f"Fetched CSV starts at {freq_min:.0f} Hz — "
            "expected a frequency response that includes frequencies below 1 kHz"
        )

    # Write in HeadMatch's standard format
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frequency_hz", "response_db"])
        for freq, val in zip(freqs, values):
            writer.writerow([float(freq), float(val)])

    return out_path


def fetch_autoeq_index() -> list[dict]:
    """Fetch and return the AutoEQ headphone index from GitHub API.

    Forces a fresh fetch from GitHub, bypassing cache.
    Raises NetworkError on connection failure.
    """
    return _fetch_and_cache_index()
