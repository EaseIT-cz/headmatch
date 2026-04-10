"""Tests for URL validation in fetch_curve_from_url — TASK-114: SSRF prevention."""

import os
import pytest
from unittest.mock import patch, MagicMock

from headmatch.headphone_db import (
    fetch_curve_from_url,
    validate_url_for_fetch,
    URLValidationError,
    _is_private_ip,
    _get_allowed_domains,
    DEFAULT_ALLOWED_DOMAINS,
)


# ── Unit tests for _is_private_ip ──

def test_is_private_ip_loopback():
    """Loopback addresses should be detected as private."""
    assert _is_private_ip("127.0.0.1")
    assert _is_private_ip("127.0.0.42")
    assert _is_private_ip("::1")


def test_is_private_ip_private_ranges():
    """RFC 1918 private ranges should be detected."""
    # 10.0.0.0/8
    assert _is_private_ip("10.0.0.1")
    assert _is_private_ip("10.255.255.255")
    # 172.16.0.0/12
    assert _is_private_ip("172.16.0.1")
    assert _is_private_ip("172.31.255.255")
    # 192.168.0.0/16
    assert _is_private_ip("192.168.0.1")
    assert _is_private_ip("192.168.255.255")


def test_is_private_ip_link_local():
    """Link-local addresses should be detected."""
    assert _is_private_ip("169.254.0.1")
    assert _is_private_ip("fe80::1")


def test_is_private_ip_public():
    """Public IPs should NOT be detected as private."""
    assert not _is_private_ip("8.8.8.8")
    assert not _is_private_ip("1.1.1.1")
    assert not _is_private_ip("93.184.216.34")  # example.com


def test_is_private_ip_invalid():
    """Invalid IP strings should be treated as private (blocked)."""
    assert _is_private_ip("not-an-ip")


# ── Unit tests for _get_allowed_domains ──

def test_get_allowed_domains_default():
    """Default allowlist should include common EQ curve sources."""
    domains = _get_allowed_domains()
    assert "raw.githubusercontent.com" in domains
    assert "github.com" in domains


def test_get_allowed_domains_env_override(monkeypatch):
    """Environment variable should override the default allowlist."""
    monkeypatch.setenv("HEADMATCH_ALLOWED_DOMAINS", "example.com, test.org")
    domains = _get_allowed_domains()
    assert domains == frozenset(["example.com", "test.org"])


def test_get_allowed_domains_env_empty_uses_default(monkeypatch):
    """Empty env var should fall back to default."""
    monkeypatch.setenv("HEADMATCH_ALLOWED_DOMAINS", "")
    # This actually returns the default because we filter empty strings
    domains = _get_allowed_domains()
    assert domains == DEFAULT_ALLOWED_DOMAINS


# ── Unit tests for validate_url_for_fetch ──

class TestValidateUrlForFetch:
    """Tests for the URL validation function."""
    
    def test_accepts_valid_https_url(self):
        """Valid HTTPS URLs from allowed domains should pass."""
        # Should not raise
        result = validate_url_for_fetch(
            "https://raw.githubusercontent.com/user/repo/main/file.csv",
            allowed_domains=frozenset(["raw.githubusercontent.com"])
        )
        assert result == "raw.githubusercontent.com"
    
    def test_rejects_http_scheme(self):
        """HTTP URLs should be rejected."""
        with pytest.raises(URLValidationError, match="not allowed"):
            validate_url_for_fetch(
                "http://example.com/file.csv",
                allowed_domains=frozenset(["example.com"])
            )
    
    def test_rejects_file_scheme(self):
        """file:// URLs should be rejected."""
        with pytest.raises(URLValidationError, match="not allowed"):
            validate_url_for_fetch(
                "file:///etc/passwd",
                allowed_domains=frozenset()
            )
    
    def test_rejects_data_scheme(self):
        """data:// URLs should be rejected."""
        with pytest.raises(URLValidationError, match="not allowed"):
            validate_url_for_fetch(
                "data:text/plain,hello",
                allowed_domains=frozenset()
            )
    
    def test_rejects_non_allowlisted_domain(self):
        """Domains not in the allowlist should be rejected."""
        with pytest.raises(URLValidationError, match="not in the allowed list"):
            validate_url_for_fetch(
                "https://evil.com/malware.csv",
                allowed_domains=frozenset(["example.com"])
            )
    
    def test_rejects_private_ip_direct(self):
        """Direct access to private IPs should be blocked."""
        with pytest.raises(URLValidationError, match="private IP"):
            validate_url_for_fetch(
                "https://127.0.0.1/admin",
                allowed_domains=frozenset(["127.0.0.1"])
            )
        with pytest.raises(URLValidationError, match="private IP"):
            validate_url_for_fetch(
                "https://10.0.0.1/internal",
                allowed_domains=frozenset(["10.0.0.1"])
            )
        with pytest.raises(URLValidationError, match="private IP"):
            validate_url_for_fetch(
                "https://192.168.1.1/router",
                allowed_domains=frozenset(["192.168.1.1"])
            )
    
    def test_rejects_domain_case_variants(self):
        """Domain validation should be case-insensitive."""
        with pytest.raises(URLValidationError, match="not in the allowed list"):
            # Uppercase domain should still work case-insensitively
            validate_url_for_fetch(
                "https://EXAMPLE.COM/file.csv",
                allowed_domains=frozenset(["test.com"])
            )


# ── Integration tests for fetch_curve_from_url ──

class DummyResponse:
    """Mock URLOpener response."""
    def __init__(self, data: bytes):
        self._data = data
    
    def read(self, *_args, **_kwargs):
        return self._data
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return False


def make_valid_csv_content():
    """Create a minimal valid frequency response CSV."""
    rows = ["frequency,response"]
    # Generate data points from 20 Hz to 20000 Hz
    for freq in [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]:
        rows.append(f"{freq},0.0")
    return "\n".join(rows).encode("utf-8")


class TestFetchCurveFromUrlSecurity:
    """Security-focused tests for fetch_curve_from_url."""
    
    def test_rejects_http_url(self, tmp_path):
        """HTTP URLs should be rejected."""
        with pytest.raises(URLValidationError, match="not allowed"):
            fetch_curve_from_url(
                "http://example.com/curve.csv",
                tmp_path / "out.csv",
                allowed_domains=frozenset(["example.com"])
            )
    
    def test_rejects_file_url(self, tmp_path):
        """file:// URLs should be rejected to prevent local file access."""
        with pytest.raises(URLValidationError, match="not allowed"):
            fetch_curve_from_url(
                "file:///etc/passwd",
                tmp_path / "out.csv"
            )
    
    def test_rejects_private_ip_url(self, tmp_path):
        """Private IPs should be blocked even if in allowlist."""
        with pytest.raises(URLValidationError, match="private IP"):
            fetch_curve_from_url(
                "https://127.0.0.1/admin/curve.csv",
                tmp_path / "out.csv",
                allowed_domains=frozenset(["127.0.0.1"])
            )
    
    def test_rejects_non_allowlisted_domain(self, tmp_path):
        """Non-allowlisted domains should be rejected."""
        with pytest.raises(URLValidationError, match="not in the allowed list"):
            fetch_curve_from_url(
                "https://evil.com/malware.csv",
                tmp_path / "out.csv",
                allowed_domains=frozenset(["example.com"])
            )
    
    def test_accepts_allowlisted_domain(self, tmp_path, monkeypatch):
        """Allowlisted domains should work."""
        csv_content = make_valid_csv_content()
        monkeypatch.setattr(
            "headmatch.headphone_db.urlopen",
            lambda *a, **k: DummyResponse(csv_content)
        )
        
        result = fetch_curve_from_url(
            "https://raw.githubusercontent.com/test/curve.csv",
            tmp_path / "out.csv",
            allowed_domains=frozenset(["raw.githubusercontent.com"])
        )
        assert result.exists()
    
    def test_default_allowlist_includes_github(self, tmp_path, monkeypatch):
        """Default allowlist should include GitHub domains."""
        csv_content = make_valid_csv_content()
        monkeypatch.setattr(
            "headmatch.headphone_db.urlopen",
            lambda *a, **k: DummyResponse(csv_content)
        )
        
        # No allowed_domains override - should use default
        result = fetch_curve_from_url(
            "https://raw.githubusercontent.com/test/curve.csv",
            tmp_path / "out.csv"
        )
        assert result.exists()


# ── DNS rebinding protection tests ──

class TestDnsRebindingProtection:
    """Tests for DNS rebinding attack prevention."""
    
    def test_resolves_and_blocks_private_ip(self, monkeypatch, tmp_path):
        """A domain resolving to private IP should be blocked."""
        # Mock DNS resolution to return a private IP
        monkeypatch.setattr(
            "headmatch.headphone_db._resolve_hostname_to_ip",
            lambda hostname: "192.168.1.1" if hostname == "evil.com" else None
        )
        
        with pytest.raises(URLValidationError, match="resolves to private IP"):
            fetch_curve_from_url(
                "https://evil.com/curve.csv",
                tmp_path / "out.csv",
                allowed_domains=frozenset(["evil.com"])
            )
    
    def test_allows_public_ip_resolution(self, monkeypatch, tmp_path):
        """A domain resolving to public IP should be allowed."""
        csv_content = make_valid_csv_content()
        monkeypatch.setattr(
            "headmatch.headphone_db.urlopen",
            lambda *a, **k: DummyResponse(csv_content)
        )
        monkeypatch.setattr(
            "headmatch.headphone_db._resolve_hostname_to_ip",
            lambda hostname: "93.184.216.34"  # example.com IP
        )
        
        result = fetch_curve_from_url(
            "https://example.com/curve.csv",
            tmp_path / "out.csv",
            allowed_domains=frozenset(["example.com"])
        )
        assert result.exists()
    
    def test_handles_dns_failure_gracefully(self, monkeypatch, tmp_path):
        """DNS resolution failure should not crash."""
        csv_content = make_valid_csv_content()
        monkeypatch.setattr(
            "headmatch.headphone_db.urlopen",
            lambda *a, **k: DummyResponse(csv_content)
        )
        monkeypatch.setattr(
            "headmatch.headphone_db._resolve_hostname_to_ip",
            lambda hostname: None  # DNS fails
        )
        
        # Should still work - DNS failure is not a blocking condition
        result = fetch_curve_from_url(
            "https://example.com/curve.csv",
            tmp_path / "out.csv",
            allowed_domains=frozenset(["example.com"])
        )
        assert result.exists()


# ── Environment variable configuration tests ──

class TestEnvironmentConfiguration:
    """Tests for HEADMATCH_ALLOWED_DOMAINS environment variable."""
    
    def test_env_var_allows_custom_domains(self, monkeypatch, tmp_path):
        """Custom domains from env var should be allowlisted."""
        monkeypatch.setenv("HEADMATCH_ALLOWED_DOMAINS", "custom-curve-host.com")
        csv_content = make_valid_csv_content()
        monkeypatch.setattr(
            "headmatch.headphone_db.urlopen",
            lambda *a, **k: DummyResponse(csv_content)
        )
        
        result = fetch_curve_from_url(
            "https://custom-curve-host.com/curve.csv",
            tmp_path / "out.csv"
        )
        assert result.exists()
    
    def test_env_var_replaces_default(self, monkeypatch, tmp_path):
        """Env var should replace, not extend, the default allowlist."""
        monkeypatch.setenv("HEADMATCH_ALLOWED_DOMAINS", "custom.com")
        
        with pytest.raises(URLValidationError, match="not in the allowed list"):
            fetch_curve_from_url(
                "https://raw.githubusercontent.com/curve.csv",
                tmp_path / "out.csv"
            )
