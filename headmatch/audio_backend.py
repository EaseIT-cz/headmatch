"""Abstract audio backend interface.

Defines the protocol for platform-specific audio I/O backends.
Concrete implementations live in backend_pipewire.py (Linux),
with backend_portaudio.py (macOS/Windows) planned.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from .signals import SweepSpec


@dataclass(frozen=True)
class AudioDevice:
    """A discovered audio device (playback or capture)."""
    kind: str           # 'playback' or 'capture'
    device_id: str      # backend-specific unique identifier
    label: str          # human-friendly display name
    description: str    # longer description or empty
    raw_info: dict      # backend-specific metadata


@dataclass(frozen=True)
class DeviceSelection:
    """Resolved playback/capture device selection."""
    playback_devices: tuple[AudioDevice, ...]
    capture_devices: tuple[AudioDevice, ...]
    selected_playback: str   # device_id
    selected_capture: str    # device_id


@dataclass(frozen=True)
class DeviceConfig:
    """User-specified output/input target identifiers."""
    output_target: Optional[str] = None
    input_target: Optional[str] = None


@dataclass(frozen=True)
class MeasurementPaths:
    """Paths for sweep WAV and recording WAV."""
    sweep_wav: Path
    recording_wav: Path


@runtime_checkable
class AudioBackend(Protocol):
    """Protocol for platform-specific audio backends."""

    name: str  # e.g. "pipewire", "portaudio"

    def discover_devices(self) -> list[AudioDevice]:
        """List available playback and capture devices."""
        ...

    def get_default_devices(self) -> dict[str, str]:
        """Return default device_ids: {'playback': ..., 'capture': ...}."""
        ...

    def resolve_device_selection(
        self,
        saved_output: Optional[str],
        saved_input: Optional[str],
    ) -> DeviceSelection:
        """Discover devices and resolve preferred targets."""
        ...

    def play_and_record(
        self,
        spec: SweepSpec,
        paths: MeasurementPaths,
        device: DeviceConfig,
    ) -> Path:
        """Play sweep and record simultaneously. Returns path to recording WAV."""
        ...

    def format_device_list(self, devices: list[AudioDevice]) -> str:
        """Format device list for CLI/human display."""
        ...

    def collect_doctor_checks(self) -> list:
        """Return backend-specific doctor checks (list of DoctorCheck)."""
        ...


def get_audio_backend() -> AudioBackend:
    """Auto-detect and return the appropriate audio backend for this platform."""
    if sys.platform == 'linux':
        from .backend_pipewire import PipeWireBackend
        return PipeWireBackend()

    if sys.platform == 'darwin':
        try:
            from .backend_portaudio import PortAudioBackend
            return PortAudioBackend()
        except ImportError:
            raise RuntimeError(
                "macOS audio backend requires the 'sounddevice' package. "
                "Install it with: pip install sounddevice"
            )

    # Fallback: try portaudio (works on Windows too)
    try:
        from .backend_portaudio import PortAudioBackend
        return PortAudioBackend()
    except ImportError:
        raise RuntimeError(
            f"No audio backend available for {sys.platform}. "
            "Install 'sounddevice' for cross-platform support, "
            "or use PipeWire on Linux."
        )
