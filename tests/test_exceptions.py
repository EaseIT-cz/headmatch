"""Tests for HeadMatch exception hierarchy."""
import pytest

from headmatch import HeadMatchError, MeasurementError, ConfigError, NetworkError


class TestExceptionHierarchy:
    """Verify exception inheritance and behavior."""

    def test_headmatch_error_is_base(self):
        """All custom exceptions inherit from HeadMatchError."""
        assert issubclass(MeasurementError, HeadMatchError)
        assert issubclass(ConfigError, HeadMatchError)
        assert issubclass(NetworkError, HeadMatchError)

    def test_measurement_error_message(self):
        """MeasurementError preserves message."""
        msg = "Invalid audio data"
        exc = MeasurementError(msg)
        assert str(exc) == msg

    def test_config_error_message(self):
        """ConfigError preserves message."""
        msg = "Config file not found"
        exc = ConfigError(msg)
        assert str(exc) == msg

    def test_network_error_message(self):
        """NetworkError preserves message."""
        msg = "Failed to fetch URL"
        exc = NetworkError(msg)
        assert str(exc) == msg


class TestMeasurementErrorRaised:
    """Verify MeasurementError is raised in measurement modules."""

    def test_io_utils_empty_csv(self, tmp_path):
        """load_fr_csv raises MeasurementError for empty CSV."""
        from headmatch.io_utils import load_fr_csv
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("frequency_hz,response_db\n")
        with pytest.raises(MeasurementError, match="No data rows found"):
            load_fr_csv(csv_path)

    def test_signals_mismatched_lengths(self):
        """fractional_octave_smoothing raises MeasurementError for mismatched arrays."""
        from headmatch.signals import fractional_octave_smoothing
        import numpy as np
        freqs = np.array([20.0, 100.0, 1000.0])
        vals = np.array([0.0, 1.0])  # Different length
        with pytest.raises(MeasurementError, match="must have the same length"):
            fractional_octave_smoothing(freqs, vals, fraction=3.0)

    def test_headphone_db_no_valid_data(self):
        """_parse_autoeq_csv raises MeasurementError for empty CSV."""
        from headmatch.headphone_db import _parse_autoeq_csv
        with pytest.raises(MeasurementError, match="No valid frequency/response data"):
            _parse_autoeq_csv("invalid,csv\nno,numbers\n")


class TestConfigErrorRaised:
    """Verify ConfigError is raised in config/validation modules."""

    def test_batch_manifest_not_found(self, monkeypatch):
        """load_batch_manifest raises ConfigError for missing file."""
        import sys
        
        # Mock yaml before importing batch (which depends on it)
        import types
        yaml_mock = types.ModuleType("yaml")
        yaml_mock.safe_load = lambda x: {}
        sys.modules["yaml"] = yaml_mock
        
        from headmatch.batch import load_batch_manifest
        with pytest.raises(ConfigError, match="Batch manifest not found"):
            load_batch_manifest("/nonexistent/path.json")

    def test_mic_cal_insufficient_points(self, tmp_path):
        """load_mic_calibration raises ConfigError for too few points."""
        from headmatch.mic_cal import load_mic_calibration
        cal_path = tmp_path / "cal.txt"
        cal_path.write_text("100 0\n")  # Only 1 point
        with pytest.raises(ConfigError, match="must contain at least 2 data points"):
            load_mic_calibration(cal_path)

    def test_batch_manifest_invalid_json(self, tmp_path):
        """load_batch_manifest raises ConfigError for invalid JSON."""
        from headmatch.batch import load_batch_manifest
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json")
        with pytest.raises(ConfigError, match="Invalid JSON in batch manifest"):
            load_batch_manifest(manifest_path)


class TestNetworkErrorRaised:
    """Verify NetworkError is raised in network modules."""

    def test_headphone_db_fetch_failure(self, monkeypatch):
        """fetch_autoeq_index raises NetworkError on connection failure."""
        import urllib.request
        import urllib.error
        
        def fake_urlopen(*args, **kwargs):
            raise urllib.error.URLError("Connection refused")
        
        # Patch urlopen in the module that uses it
        monkeypatch.setattr("headmatch.headphone_db.urlopen", fake_urlopen)
        
        # Also clear cache
        from headmatch import headphone_db
        monkeypatch.setattr(headphone_db, "_load_cached_index", lambda: None)
        
        with pytest.raises(NetworkError, match="Failed to fetch"):
            headphone_db.fetch_autoeq_index()

    def test_fetch_curve_from_url_non_https(self):
        """fetch_curve_from_url raises NetworkError for non-HTTPS URLs."""
        from headmatch.headphone_db import fetch_curve_from_url
        with pytest.raises(NetworkError, match="Only HTTPS URLs are accepted"):
            fetch_curve_from_url("http://example.com/data.csv", "/tmp/out.csv")