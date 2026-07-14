"""Tests for SSRF URL validation in headphone_db.py — TASK-114."""

import socket
import pytest
from unittest.mock import patch
from urllib.error import HTTPError

from headmatch.exceptions import MeasurementError, NetworkError
from headmatch.headphone_db import (
    ALLOWED_DOMAINS,
    fetch_curve_from_url,
    _parse_autoeq_csv,
    _validate_url_for_ssrf,
    _is_private_ip,
)


class TestAllowedDomains:
    """Tests for the ALLOWED_DOMAINS constant."""

    def test_contains_exact_github_hosts(self):
        """The allowlist should contain only the expected GitHub hosts."""
        assert ALLOWED_DOMAINS == ("raw.githubusercontent.com", "api.github.com")


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

    def test_non_global_ips_are_blocked(self):
        """Reserved, unspecified, and multicast ranges are not safe SSRF targets."""
        assert _is_private_ip("0.0.0.0") is True
        assert _is_private_ip("224.0.0.1") is True
        assert _is_private_ip("240.0.0.1") is True
        assert _is_private_ip("::1") is True

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
        with pytest.raises(NetworkError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("http://raw.githubusercontent.com/file.csv")

    def test_rejects_file_scheme(self):
        """file:// scheme should be rejected."""
        with pytest.raises(NetworkError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("file:///etc/passwd")

    def test_rejects_ftp_scheme(self):
        """ftp:// scheme should be rejected."""
        with pytest.raises(NetworkError, match="scheme must be 'https'"):
            _validate_url_for_ssrf("ftp://example.com/file.csv")

    def test_rejects_unknown_domain(self):
        """Unknown domains should be rejected."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://evil.com/malicious.csv")

    def test_rejects_subdomain_of_allowed(self):
        """Subdomains of allowed domains should be rejected (prevents bypass)."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com.evil.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_private_ip_resolution(self, mock_getaddrinfo):
        """URLs resolving to private IPs should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]
        with pytest.raises(NetworkError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_loopback_resolution(self, mock_getaddrinfo):
        """URLs resolving to loopback should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with pytest.raises(NetworkError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_link_local_resolution(self, mock_getaddrinfo):
        """URLs resolving to link-local should be rejected."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.0.1", 443))]
        with pytest.raises(NetworkError, match="resolves to private IP"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_rejects_invalid_hostname(self, mock_getaddrinfo):
        """Malformed hostnames should raise NetworkError."""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
        with pytest.raises(NetworkError, match="Could not resolve"):
            _validate_url_for_ssrf("https://raw.githubusercontent.com/file.csv")

    def test_rejects_missing_hostname(self):
        """URLs without hostnames should be rejected."""
        with pytest.raises(NetworkError, match="valid hostname"):
            _validate_url_for_ssrf("https:///path/to/file.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_case_insensitive_domain_matching(self, mock_getaddrinfo):
        """Domain matching should be case-insensitive."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        url = "https://RAW.GITHUBUSERCONTENT.COM/user/repo/file.csv"
        result = _validate_url_for_ssrf(url)
        assert result == url

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_accepts_urls_with_paths_and_query_params(self, mock_getaddrinfo):
        """URLs with paths and query parameters on allowed domains should be accepted."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        # URL with deep path and query parameters
        url = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/oratory1990/harman_over-ear_2018/HD600/HD600.csv?token=abc123&ref=main"
        result = _validate_url_for_ssrf(url)
        assert result == url

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_accepts_api_github_with_query_params(self, mock_getaddrinfo):
        """api.github.com URLs with query parameters should be accepted."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.5", 443))]
        url = "https://api.github.com/repos/owner/repo/contents/file.csv?ref=main&recursive=1"
        result = _validate_url_for_ssrf(url)
        assert result == url

    def test_rejects_private_ip_host_direct(self):
        """URLs with direct private IP hosts should be rejected (192.168.x.x)."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://192.168.1.1/data.csv")

    def test_rejects_private_ip_host_10_x(self):
        """URLs with direct private IP hosts should be rejected (10.x.x.x)."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://10.0.0.1/data.csv")

    def test_rejects_loopback_ip_direct(self):
        """URLs with direct loopback IP should be rejected (127.0.0.1)."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://127.0.0.1/data.csv")

    def test_rejects_loopback_localhost(self):
        """URLs with localhost should be rejected."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://localhost/data.csv")

    def test_rejects_link_local_ip_direct(self):
        """URLs with direct link-local IP should be rejected (169.254.x.x)."""
        with pytest.raises(NetworkError, match="not in the allowed list"):
            _validate_url_for_ssrf("https://169.254.1.1/data.csv")

    @patch("headmatch.headphone_db.socket.getaddrinfo")
    def test_accepts_port_specification_with_allowed_domain(self, mock_getaddrinfo):
        """URLs with port specification on allowed domains should be accepted."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        url = "https://raw.githubusercontent.com:443/user/repo/file.csv"
        result = _validate_url_for_ssrf(url)
        assert result == url


class TestFetchCurveRedirectSafety:
    @patch("headmatch.headphone_db.socket.getaddrinfo")
    @patch("headmatch.headphone_db._NO_REDIRECT_OPENER.open")
    def test_rejects_redirects_before_reading_body(self, mock_open, mock_getaddrinfo, tmp_path):
        """Allowed hosts must not be able to redirect the fetcher to internal URLs."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.199.108.133", 443))]
        mock_open.side_effect = HTTPError(
            "https://raw.githubusercontent.com/user/repo/file.csv",
            302,
            "Found",
            {"Location": "http://169.254.169.254/latest/meta-data/"},
            None,
        )

        with pytest.raises(NetworkError, match="Redirects are not allowed"):
            fetch_curve_from_url(
                "https://raw.githubusercontent.com/user/repo/file.csv",
                tmp_path / "out.csv",
            )

    def test_rejects_unsorted_remote_csv(self):
        with pytest.raises(MeasurementError, match="strictly increasing"):
            _parse_autoeq_csv("20,0\n100,1\n50,2\n")

    def test_rejects_duplicate_remote_csv_frequency(self):
        with pytest.raises(MeasurementError, match="duplicate"):
            _parse_autoeq_csv("20,0\n20,1\n100,2\n")

    def test_rejects_non_finite_remote_csv_value(self):
        with pytest.raises(MeasurementError, match="non-finite"):
            _parse_autoeq_csv("20,0\n100,nan\n1000,2\n")
