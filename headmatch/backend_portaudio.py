"""PortAudio audio backend for macOS, Windows, and Linux fallback.

Implements the AudioBackend protocol using the ``sounddevice`` library
(a Python wrapper around PortAudio). This enables HeadMatch to work
on macOS (CoreAudio) and Windows (WASAPI/WDM-KS) without PipeWire.

Install with: pip install headmatch[portaudio]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np

from .audio_backend import AudioBackend, AudioDevice, DeviceConfig, DeviceSelection, MeasurementPaths
from .signals import SweepSpec


def _import_sd():
    """Import sounddevice with a clear error if unavailable."""
    try:
        import sounddevice as sd
        return sd
    except OSError as exc:
        raise RuntimeError(
            "PortAudio library not found. "
            "On macOS: brew install portaudio && pip install sounddevice. "
            "On Windows: pip install sounddevice (ships bundled PortAudio)."
        ) from exc
    except ImportError as exc:
        raise RuntimeError(
            "sounddevice is not installed. Install with: pip install headmatch[portaudio]"
        ) from exc


def _classify_device(info: dict) -> Optional[str]:
    """Classify a sounddevice device dict as 'playback', 'capture', or None."""
    max_out = info.get("max_output_channels", 0)
    max_in = info.get("max_input_channels", 0)
    # Devices can be both input and output; classify by primary role
    if max_out > 0 and max_in > 0:
        return None  # duplex — list as both below
    if max_out > 0:
        return "playback"
    if max_in > 0:
        return "capture"
    return None


def _device_to_audio_devices(index: int, info: dict) -> list[AudioDevice]:
    """Convert a sounddevice device dict into AudioDevice(s).

    A duplex device (both input and output) produces two entries.
    """
    devices = []
    name = info.get("name", f"Device {index}")
    max_out = info.get("max_output_channels", 0)
    max_in = info.get("max_input_channels", 0)
    host_api = info.get("hostapi", -1)

    raw = {
        "index": index,
        "hostapi": host_api,
        "default_samplerate": info.get("default_samplerate", 0),
        "max_input_channels": max_in,
        "max_output_channels": max_out,
    }

    if max_out > 0:
        devices.append(AudioDevice(
            kind="playback",
            device_id=str(index),
            label=name,
            description=f"{name} ({max_out}ch out)",
            raw_info={**raw, "role": "playback"},
        ))
    if max_in > 0:
        devices.append(AudioDevice(
            kind="capture",
            device_id=str(index),
            label=name,
            description=f"{name} ({max_in}ch in)",
            raw_info={**raw, "role": "capture"},
        ))
    return devices


def _resolve_target(kind: str, saved: Optional[str], devices: list[AudioDevice], default_id: Optional[str]) -> str:
    """Resolve a device target by saved preference, default, or first match."""
    matching = [d for d in devices if d.kind == kind]
    saved_str = (saved or "").strip()

    if saved_str:
        # Try exact device_id match first
        for d in matching:
            if d.device_id == saved_str:
                return d.device_id
        # Then substring match on label
        for d in matching:
            if saved_str.lower() in d.label.lower():
                return d.device_id

    default_str = (default_id or "").strip()
    if default_str:
        for d in matching:
            if d.device_id == default_str:
                return d.device_id

    if matching:
        return matching[0].device_id
    return ""


class PortAudioBackend:
    """AudioBackend implementation using sounddevice (PortAudio)."""

    name = "portaudio"

    def discover_devices(self) -> list[AudioDevice]:
        sd = _import_sd()
        all_info = sd.query_devices()
        devices: list[AudioDevice] = []
        if isinstance(all_info, dict):
            # Single device — shouldn't happen with query_devices() no args
            all_info = [all_info]
        for idx, info in enumerate(all_info):
            if not isinstance(info, dict):
                continue
            devices.extend(_device_to_audio_devices(idx, info))
        devices.sort(key=lambda d: (d.kind, d.label.lower()))
        return devices

    def get_default_devices(self) -> dict[str, str]:
        sd = _import_sd()
        defaults: dict[str, str] = {}
        try:
            default_in, default_out = sd.default.device
            if default_out is not None and default_out >= 0:
                defaults["playback"] = str(default_out)
            if default_in is not None and default_in >= 0:
                defaults["capture"] = str(default_in)
        except Exception:
            pass
        return defaults

    def resolve_device_selection(
        self,
        saved_output: Optional[str],
        saved_input: Optional[str],
    ) -> DeviceSelection:
        try:
            devices = self.discover_devices()
        except RuntimeError:
            devices = []
        defaults = self.get_default_devices()
        return DeviceSelection(
            playback_devices=tuple(d for d in devices if d.kind == "playback"),
            capture_devices=tuple(d for d in devices if d.kind == "capture"),
            selected_playback=_resolve_target("playback", saved_output, devices, defaults.get("playback")),
            selected_capture=_resolve_target("capture", saved_input, devices, defaults.get("capture")),
        )

    def play_and_record(
        self,
        spec: SweepSpec,
        paths: MeasurementPaths,
        device: DeviceConfig,
    ) -> Path:
        sd = _import_sd()
        from .measure import render_sweep_file
        from .io_utils import write_wav

        paths.sweep_wav.parent.mkdir(parents=True, exist_ok=True)
        paths.recording_wav.parent.mkdir(parents=True, exist_ok=True)
        render_sweep_file(spec, paths.sweep_wav)

        # Read the sweep WAV
        from .io_utils import read_wav
        sweep_data, sr = read_wav(paths.sweep_wav)
        if sr != spec.sample_rate:
            raise RuntimeError(
                f"Sweep sample rate mismatch: expected {spec.sample_rate}, got {sr}"
            )

        # Resolve device indices
        output_device = None
        input_device = None
        if device.output_target:
            try:
                output_device = int(device.output_target)
            except ValueError:
                # Try to find by name
                output_device = device.output_target
        if device.input_target:
            try:
                input_device = int(device.input_target)
            except ValueError:
                input_device = device.input_target

        # Query device capabilities to avoid channel/samplerate mismatches
        try:
            out_info = sd.query_devices(output_device, kind='output')
            in_info = sd.query_devices(input_device, kind='input')
        except Exception:
            out_info, in_info = {}, {}

        out_channels = min(2, out_info.get('max_output_channels', 2))
        in_channels = min(2, in_info.get('max_input_channels', 2))

        # If output is mono, downmix the stereo sweep
        if out_channels == 1 and sweep_data.ndim == 2 and sweep_data.shape[1] >= 2:
            play_data = sweep_data.mean(axis=1, keepdims=True)
        else:
            play_data = sweep_data

        # Simultaneous play and record
        try:
            recording = sd.playrec(
                play_data,
                samplerate=spec.sample_rate,
                channels=in_channels,
                device=(input_device, output_device),
                blocking=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Audio playback/recording failed: {exc}. "
                "Check your audio devices with 'headmatch list-targets'."
            ) from exc

        if recording is None or len(recording) == 0:
            raise RuntimeError(
                "Recording produced no data. "
                "Check your audio device selection with 'headmatch list-targets'."
            )

        # Ensure stereo float64
        recording = np.asarray(recording, dtype=np.float64)
        if recording.ndim == 1:
            recording = np.column_stack([recording, recording])

        write_wav(paths.recording_wav, recording, spec.sample_rate)

        if not paths.recording_wav.exists() or paths.recording_wav.stat().st_size == 0:
            raise RuntimeError(
                "Recording file was not written. "
                "Check audio device permissions and try again."
            )
        return paths.recording_wav

    def format_device_list(self, devices: list[AudioDevice]) -> str:
        lines = [
            "Audio targets you can pass to --output-target / --input-target",
            "",
            "Use the device ID (number) after the arrow.",
            "",
        ]
        grouped = {
            "playback": [d for d in devices if d.kind == "playback"],
            "capture": [d for d in devices if d.kind == "capture"],
        }
        for kind, title in (("playback", "Playback targets (--output-target)"), ("capture", "Capture targets (--input-target)")):
            lines.append(title)
            if kind == "playback":
                lines.append("  Choose the output device connected to your headphones or speakers.")
            else:
                lines.append("  Choose the input device connected to your measurement microphone.")
            entries = grouped[kind]
            if not entries:
                lines.append("  (none found)")
            else:
                for d in entries:
                    sr = d.raw_info.get("default_samplerate", "")
                    extra = f" [{sr:.0f} Hz]" if sr else ""
                    lines.append(f"  - {d.label} -> {d.device_id}{extra}")
            lines.append("")
        lines.extend([
            "Example:",
            "  headmatch measure --out-dir out/session_01 --output-target 2 --input-target 1",
            "",
            "Tip: use the device number. Run this command to see what's available.",
        ])
        return "\n".join(lines)

    def collect_doctor_checks(self) -> list:
        from .measure import DoctorCheck

        checks = []

        # Check sounddevice availability
        try:
            sd = _import_sd()
            checks.append(DoctorCheck(
                name="sounddevice",
                ok=True,
                detail=f"sounddevice {getattr(sd, '__version__', 'unknown')} with PortAudio",
            ))
        except RuntimeError as exc:
            checks.append(DoctorCheck(
                name="sounddevice",
                ok=False,
                detail=str(exc),
                action="Install sounddevice: pip install headmatch[portaudio]",
            ))
            return checks  # Can't check further without sounddevice

        # Check device discovery
        try:
            devices = self.discover_devices()
            playback = sum(d.kind == "playback" for d in devices)
            capture = sum(d.kind == "capture" for d in devices)
            ok = playback > 0 and capture > 0
            detail = f"Found {playback} playback and {capture} capture device(s)."
            action = None if ok else "Connect an audio output and input device, then try 'headmatch list-targets'."
            checks.append(DoctorCheck(name="audio discovery", ok=ok, detail=detail, action=action))
        except RuntimeError as exc:
            checks.append(DoctorCheck(
                name="audio discovery",
                ok=False,
                detail=str(exc),
                action="Check PortAudio installation and audio device connections.",
            ))

        return checks
