"""Tests for the HeadMatch exception hierarchy."""

import pytest

from headmatch import ConfigError, HeadMatchError, MeasurementError, NetworkError


class TestExceptionHierarchy:
    """Test the exception class hierarchy and basic properties."""

    def test_headmatch_error_is_exception_subclass(self):
        """HeadMatchError is a subclass of Exception."""
        assert issubclass(HeadMatchError, Exception)

    def test_measurement_error_is_headmatch_error_subclass(self):
        """MeasurementError is a subclass of HeadMatchError."""
        assert issubclass(MeasurementError, HeadMatchError)

    def test_config_error_is_headmatch_error_subclass(self):
        """ConfigError is a subclass of HeadMatchError."""
        assert issubclass(ConfigError, HeadMatchError)

    def test_network_error_is_headmatch_error_subclass(self):
        """NetworkError is a subclass of HeadMatchError."""
        assert issubclass(NetworkError, HeadMatchError)

    def test_headmatch_error_can_be_caught(self):
        """All subclasses can be caught as HeadMatchError."""
        errors = [MeasurementError, ConfigError, NetworkError]
        for err_cls in errors:
            try:
                raise err_cls("test message")
            except HeadMatchError as e:
                assert str(e) == "test message"

    def test_all_exceptions_inherit_from_base(self):
        """Verify all three subclasses are HeadMatchError subclasses."""
        subclasses = [MeasurementError, ConfigError, NetworkError]
        for subclass in subclasses:
            assert subclass.__bases__ == (HeadMatchError,)