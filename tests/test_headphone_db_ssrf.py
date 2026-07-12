"""Tests for SSRF URL validation in headphone_db.py — TASK-114."""

import socket
import pytest
from unittest.mock import patch

from headmatch.headphone_db import (
    ALLOWED_DOMAINS,
    _validate_url_for_ssrf,
    _is_private_ip,
)


class TestAllowedDomains:
    """Tests for the ALLOWED_DOMAINS constant."""

    def test_contains_raw_githubusercontent(self):
        """raw.githubusercontent.com should be in allowed domains."""
        assert "raw.githubusercontent.com" in ALLOWED_DOMAINS

    def test_contains_api_github(self):
        """api.github.com should be in allowed domains."""
        assert "api.github.com" in ALLOWED_DOMAINS


class TestIsPrivateIp:
    """Tests for the _is_private_ip helper."""

    def test_private_10_x_x_x(self):
        """10.x.x.x addresses are private."""
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("10.255.255.255") is True

    def test_private_172_16_31_range(self):
        """172.16.x.x through 172.31.x.x addresses are private."""
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.20.1.1") is True
        assert _is_private_ip("172.31.255.255") is True

    def test_private_192_168_x_x(self):
        """192.168.x.x addresses are private."""
        assert _is_private_ip("192.168.0.1") is True
        assert _is_private_ip("192.168.255.255") is True

    def test_loopback_127_x_x_x(self):
        """127.x.x.x addresses are loopback."""
        assert _is_private_ip("127.0.0.1") is True
        assert _is_private_ip("127.255.255.255") is True

    def test_link_local_169_254(self):
        """169.254.x.x addresses are link-local."""
        assert _is_private_ip("169.254.0.1") is True
        assert _is_private_ip("169.254.255.255") is True

    def test_public_ip_not_private(self):
        """Public IPs should not be flagged as private."""
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("1.1.1.1") is False
        assert _is_private_ip("185.199.108.133") is False

    def test_invalid_ip_returns_false(self):
        """Invalid IP strings should return False."""
        assert _is_private_ip("not-an-ip") is False
        assert _is_private_ip("") is False


class TestValidateUrlForSsrf:
    """Tests for the _validate_url_for_ssrf function."""

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_accepts_https_raw_githubusercontent(self, mock_getaddrinfo):
        """Allowlist should accept raw.githubusercontent.com URLs."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        url = "https://raw.githubusercontent.com/user/repo/file.csv"
        result = _validate_url_for_ssrf(url)
        assert result == url

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_accepts_https_api_github(self, mock_getaddrinfo):
        """Allowlist should accept api.github.com URLs."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.5", 443))]
        url = "https://api.github.com/repos/owner/repo/contents/file.csv"
        result = _validate_url_for_ssrf(url)
        assert result == url

    def test_rejects_http_scheme(self):
        """HTTP scheme should be rejected."""
        with pytest.raises(ValueError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("http://raw.githubusercontent.com/file.csv")

    def test_rejects_file_scheme(self):
        """file:// scheme should be rejected."""
        with pytest.raises(ValueError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("file:///etc/passwd")

    def test_rejects_ftp_scheme(self):
        """ftp:// scheme should be rejected."""
        with pytest.raises(ValueError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("ftp://example.com/file.csv")

    def test_rejects_unknown_domain(self):
        """Unknown domains should be rejected."""
        with pytest.raises(ValueError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://evil.com/malicious.csv")

    def test_rejects_subdomain_of_allowed(self):
        """Subdomains of allowed domains should be rejected (prevents bypass)."""
        with pytest.raises(ValueError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com.evil.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_private_ip_resolution(self, mock_getaddrinfo):
        """URLs resolving to private IPs should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]
        with pytest.raises(ValueError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_loopback_resolution(self, mock_getaddrinfo):
        """URLs resolving to loopback should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with pytest.raises(ValueError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_link_local_resolution(self, mock_getaddrinfo):
        """URLs resolving to link-local should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.0.1", 443))]
        with pytest.raises(ValueError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_invalid_hostname(self, mock_getaddrinfo):
        """Malformed hostnames should raise ValueError."""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
        with pytest.raises(ValueError, match="Could not resolve"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    def test_rejects_missing_hostname(self):
        """URLs without hostnames should be rejected."""
        with pytest.raises(ValueError, match="valid hostname"):
            _validate_url_for_ssrf("https:///path/to/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_case_insensitive_domain_matching(self, mock_getaddrinfo):
        """Domain matching should be case-insensitive."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        url = "https://RAW.GITHUBUSERCONTENT.COM/user/repo/file.csv"
        result = _validate_url_for_ssrf(url)
        assert result == url