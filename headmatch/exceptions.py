"""HeadMatch exception hierarchy.

All exceptions raised by HeadMatch inherit from HeadMatchError
for easy catching and identification.
"""


class HeadMatchError(Exception):
    """Base class for all HeadMatch exceptions."""
    pass


class MeasurementError(HeadMatchError):
    """Invalid measurement data or audio processing failure.

    Raised when:
    - Audio data is invalid (wrong shape, empty, mono when stereo expected)
    - Frequency response data fails validation (non-finite, non-positive freqs)
    - Sample rate or sweep parameters are invalid
    - Audio backend fails (playback/recording error)
    """
    pass


class ConfigError(HeadMatchError):
    """Invalid configuration or file format.

    Raised when:
    - Config JSON is malformed or missing required fields
    - Batch manifest is invalid
    - Calibration file is malformed
    - Required files are missing (config, manifest)
    - Unknown built-in target requested
    """
    pass


class NetworkError(HeadMatchError):
    """Network or remote resource failure.

    Raised when:
    - GitHub API requests fail
    - Remote CSV/URL fetch fails
    """
    pass