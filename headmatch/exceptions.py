"""HeadMatch exception hierarchy.

This module provides a structured exception hierarchy rooted in HeadMatchError
with domain-specific subclasses for measurement, validation, configuration,
network, audio backend, and user input errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class HeadMatchError(Exception):
    """Base class for all HeadMatch domain errors.

    Attributes:
        message: Human-readable error description
        context: Optional dict with structured context (paths, URLs, devices)
        cause: Original exception if wrapping
    """

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.__cause__ = cause

    def __str__(self) -> str:
        if self.context:
            ctx_str = " | " + ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message}{ctx_str}"
        return self.message

    def to_dict(self) -> dict:
        """Serialize for JSON export or logging."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "context": self.context,
        }


# =============================================================================
# Measurement Errors
# =============================================================================


class MeasurementError(HeadMatchError):
    """Base for measurement-time errors."""

    pass


class AudioFormatError(MeasurementError):
    """Raised when audio data has invalid dimensions or channels.

    Context attributes:
        path: Path to the audio file
        expected: Expected format (e.g., "stereo", "2D array")
        actual: Actual format found
    """

    pass


class MeasurementTooShortError(MeasurementError):
    """Raised when recording is shorter than the minimum expected length.

    Context attributes:
        path: Path to recording
        actual_samples: Actual number of samples
        expected_samples: Minimum expected samples
    """

    pass


class SampleRateMismatchError(MeasurementError):
    """Raised when recording sample rate doesn't match sweep specification.

    Context attributes:
        path: Path to recording
        actual_sr: Actual sample rate
        expected_sr: Expected sample rate
    """

    pass


class AlignmentError(MeasurementError):
    """Raised when sweep alignment fails."""

    pass


class DuplicatedChannelError(MeasurementError):
    """Raised when left and right audio channels are identical."""

    def __init__(
        self,
        message: str,
        *,
        path: str | Path | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context = {"path": str(path) if path else None}
        if context:
            merged_context.update(context)
        super().__init__(message, context=merged_context)
        self.path = path


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(HeadMatchError):
    """Base for data validation errors."""

    pass


class FrequencyResponseError(ValidationError):
    """Raised for invalid frequency response data.

    Context attributes:
        path: CSV file path
        issue: Specific issue (e.g., "non_positive_frequencies", "nan_values", "duplicate_frequencies")
    """

    pass


class CurveNormalizationError(ValidationError):
    """Raised when a target curve cannot be normalized at 1 kHz.

    Context attributes:
        path: Curve file path
        freq_min: Lowest frequency in curve
        freq_max: Highest frequency in curve
    """

    pass


class CSVFormatError(ValidationError):
    """Raised for CSV parsing failures.

    Context attributes:
        path: CSV file path
        expected_columns: List of expected column names
        missing_column: Specific missing column, if applicable
    """

    pass


class TargetCurveError(ValidationError):
    """Raised for target curve validation failures.

    Context attributes:
        source: Source curve path
        target: Target curve path
        issue: Specific issue (e.g., "source_equals_target", "file_overwrite")
    """

    pass


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(HeadMatchError):
    """Base for configuration-related errors."""

    pass


class ConfigParseError(ConfigurationError):
    """Raised when config file cannot be parsed.

    Context attributes:
        path: Config file path
        line: Line number if parse error
    """

    pass


class ManifestError(ConfigurationError):
    """Raised for batch manifest validation failures.

    Context attributes:
        path: Manifest file path
        entry_index: Index of invalid entry (if applicable)
        field: Missing or invalid field
    """

    pass


class MissingExecutableError(ConfigurationError):
    """Raised when a required external executable is not found.

    Context attributes:
        executable: Name of missing executable
        install_hint: Installation instructions
    """

    def __init__(self, executable: str, install_hint: str | None = None):
        message = f"Required executable not found: {executable}"
        super().__init__(
            message,
            context={"executable": executable, "install_hint": install_hint},
        )
        self.executable = executable
        self.install_hint = install_hint


# =============================================================================
# Network Errors
# =============================================================================


class NetworkError(HeadMatchError):
    """Base for network-related errors."""

    pass


class URLValidationError(NetworkError, ValueError):
    """Raised when a URL fails SSRF validation.

    Dual inheritance from ValueError for backward compatibility with existing code.

    Context attributes:
        url: The rejected URL
        reason: Specific reason (private_ip, invalid_scheme, domain_not_allowed)
    """

    pass


class FetchError(NetworkError):
    """Raised when a network fetch fails.

    Context attributes:
        url: URL that failed
        status_code: HTTP status (if applicable)
        reason: Underlying error message
    """

    pass


# =============================================================================
# Audio Backend Errors
# =============================================================================


class AudioBackendError(HeadMatchError):
    """Base for audio I/O errors."""

    pass


class BackendNotAvailableError(AudioBackendError):
    """Raised when no audio backend is available for the platform.

    Context attributes:
        platform: Current OS platform
        hint: Installation instructions
    """

    pass


class DeviceNotFoundError(AudioBackendError):
    """Raised when a specified audio device cannot be found.

    Context attributes:
        device_id: Requested device ID
        kind: "playback" or "capture"
    """

    pass


class AudioStreamError(AudioBackendError):
    """Raised when audio playback or recording fails."""

    pass


# =============================================================================
# User Input Errors
# =============================================================================


class UserInputError(HeadMatchError):
    """Base for user input validation errors."""

    pass


class PathRequiredError(UserInputError):
    """Raised when a required path is missing.

    Context attributes:
        field_name: Name of the missing field
    """

    pass


class InvalidInputError(UserInputError):
    """Generic user input validation failure."""

    pass


__all__ = [
    # Base
    "HeadMatchError",
    # Measurement
    "MeasurementError",
    "AudioFormatError",
    "MeasurementTooShortError",
    "SampleRateMismatchError",
    "AlignmentError",
    "DuplicatedChannelError",
    # Validation
    "ValidationError",
    "FrequencyResponseError",
    "CurveNormalizationError",
    "CSVFormatError",
    "TargetCurveError",
    # Configuration
    "ConfigurationError",
    "ConfigParseError",
    "ManifestError",
    "MissingExecutableError",
    # Network
    "NetworkError",
    "URLValidationError",
    "FetchError",
    # Audio Backend
    "AudioBackendError",
    "BackendNotAvailableError",
    "DeviceNotFoundError",
    "AudioStreamError",
    # User Input
    "UserInputError",
    "PathRequiredError",
    "InvalidInputError",
]
