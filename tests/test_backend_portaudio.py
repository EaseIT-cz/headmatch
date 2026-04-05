"""Tests for PortAudio audio backend — all sounddevice calls are mocked."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

from headmatch.audio_backend import AudioDevice, DeviceConfig, MeasurementPaths
from headmatch.backend_portaudio import (
    PortAudioBackend,
    _classify_device,
    _device_to_audio_devices,
    _resolve_target,
    _import_sd,
)


# ── Device classification tests ──

def test_classify_output_only():
    assert _classify_device({"max_output_channels": 2, "max_input_channels": 0}) == "playback"

def test_classify_input_only():
    assert _classify_device({"max_output_channels": 0, "max_input_channels": 2}) == "capture"

def test_classify_duplex():
    # Duplex devices return None — they're split into two entries by _device_to_audio_devices
    assert _classify_device({"max_output_channels": 2, "max_input_channels": 2}) is None

def test_classify_no_channels():
    assert _classify_device({"max_output_channels": 0, "max_input_channels": 0}) is None


# ── Device conversion tests ──

def test_device_to_audio_devices_output():
    devices = _device_to_audio_devices(0, {
        "name": "MacBook Pro Speakers",
        "max_output_channels": 2,
        "max_input_channels": 0,
        "hostapi": 0,
        "default_samplerate": 48000.0,
    })
    assert len(devices) == 1
    assert devices[0].kind == "playback"
    assert devices[0].device_id == "0"
    assert devices[0].label == "MacBook Pro Speakers"

def test_device_to_audio_devices_duplex():
    devices = _device_to_audio_devices(3, {
        "name": "USB Audio Interface",
        "max_output_channels": 2,
        "max_input_channels": 2,
        "hostapi": 0,
        "default_samplerate": 96000.0,
    })
    assert len(devices) == 2
    kinds = {d.kind for d in devices}
    assert kinds == {"playback", "capture"}
    assert all(d.device_id == "3" for d in devices)


# ── Target resolution tests ──

def test_resolve_target_by_saved_id():
    devices = [
        AudioDevice("playback", "0", "Speakers", "", {}),
        AudioDevice("playback", "2", "USB DAC", "", {}),
    ]
    assert _resolve_target("playback", "2", devices, "0") == "2"

def test_resolve_target_by_saved_label():
    devices = [
        AudioDevice("playback", "0", "Speakers", "", {}),
        AudioDevice("playback", "2", "USB DAC", "", {}),
    ]
    assert _resolve_target("playback", "USB DAC", devices, None) == "2"

def test_resolve_target_falls_back_to_default():
    devices = [
        AudioDevice("playback", "0", "Speakers", "", {}),
        AudioDevice("playback", "2", "USB DAC", "", {}),
    ]
    assert _resolve_target("playback", None, devices, "2") == "2"

def test_resolve_target_falls_back_to_first():
    devices = [
        AudioDevice("playback", "0", "Speakers", "", {}),
        AudioDevice("playback", "2", "USB DAC", "", {}),
    ]
    assert _resolve_target("playback", None, devices, "99") == "0"

def test_resolve_target_empty_when_no_devices():
    assert _resolve_target("capture", "1", [], None) == ""


# ── Backend discover_devices (mocked) ──

MOCK_DEVICES = [
    {"name": "Built-in Output", "max_output_channels": 2, "max_input_channels": 0,
     "hostapi": 0, "default_samplerate": 44100.0},
    {"name": "Built-in Microphone", "max_output_channels": 0, "max_input_channels": 2,
     "hostapi": 0, "default_samplerate": 44100.0},
    {"name": "USB Audio", "max_output_channels": 2, "max_input_channels": 2,
     "hostapi": 0, "default_samplerate": 48000.0},
]


@patch("headmatch.backend_portaudio._import_sd")
def test_discover_devices(mock_sd_factory):
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = MOCK_DEVICES
    mock_sd_factory.return_value = mock_sd

    backend = PortAudioBackend()
    devices = backend.discover_devices()

    playback = [d for d in devices if d.kind == "playback"]
    capture = [d for d in devices if d.kind == "capture"]
    assert len(playback) == 2  # Built-in Output + USB Audio
    assert len(capture) == 2   # Built-in Microphone + USB Audio


@patch("headmatch.backend_portaudio._import_sd")
def test_get_default_devices(mock_sd_factory):
    mock_sd = MagicMock()
    mock_sd.default.device = (1, 0)  # (input, output)
    mock_sd_factory.return_value = mock_sd

    backend = PortAudioBackend()
    defaults = backend.get_default_devices()
    assert defaults["playback"] == "0"
    assert defaults["capture"] == "1"


@patch("headmatch.backend_portaudio._import_sd")
def test_resolve_device_selection(mock_sd_factory):
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = MOCK_DEVICES
    mock_sd.default.device = (1, 0)
    mock_sd_factory.return_value = mock_sd

    backend = PortAudioBackend()
    sel = backend.resolve_device_selection(saved_output="USB", saved_input=None)
    assert sel.selected_playback == "2"  # USB Audio matched by label substring
    assert sel.selected_capture == "1"   # default


# ── play_and_record (mocked) ──

@patch("headmatch.backend_portaudio._import_sd")
def test_play_and_record(mock_sd_factory, tmp_path):
    mock_sd = MagicMock()
    fake_recording = np.random.randn(48000, 2).astype(np.float64)
    mock_sd.playrec.return_value = fake_recording
    mock_sd.query_devices.side_effect = lambda dev, kind=None: {
        "max_output_channels": 2, "max_input_channels": 2, "default_samplerate": 48000.0,
    }
    mock_sd_factory.return_value = mock_sd

    from headmatch.signals import SweepSpec
    spec = SweepSpec(sample_rate=48000, duration_s=1.0)
    paths = MeasurementPaths(
        sweep_wav=tmp_path / "sweep.wav",
        recording_wav=tmp_path / "recording.wav",
    )
    device = DeviceConfig(output_target="0", input_target="1")

    backend = PortAudioBackend()
    result = backend.play_and_record(spec, paths, device)

    assert result == paths.recording_wav
    assert paths.recording_wav.exists()
    assert paths.recording_wav.stat().st_size > 0
    mock_sd.playrec.assert_called_once()


@patch("headmatch.backend_portaudio._import_sd")
def test_play_and_record_with_name_targets(mock_sd_factory, tmp_path):
    mock_sd = MagicMock()
    fake_recording = np.random.randn(48000, 2).astype(np.float64)
    mock_sd.playrec.return_value = fake_recording
    mock_sd.query_devices.side_effect = lambda dev, kind=None: {
        "max_output_channels": 2, "max_input_channels": 2, "default_samplerate": 48000.0,
    }
    mock_sd_factory.return_value = mock_sd

    from headmatch.signals import SweepSpec
    spec = SweepSpec(sample_rate=48000, duration_s=1.0)
    paths = MeasurementPaths(
        sweep_wav=tmp_path / "sweep.wav",
        recording_wav=tmp_path / "recording.wav",
    )
    device = DeviceConfig(output_target="USB Audio", input_target="Built-in Mic")

    backend = PortAudioBackend()
    result = backend.play_and_record(spec, paths, device)
    assert result == paths.recording_wav

    # Device args should be strings (names), not ints
    call_kwargs = mock_sd.playrec.call_args
    device_arg = call_kwargs.kwargs.get("device") or call_kwargs[1].get("device")
    assert device_arg == ("Built-in Mic", "USB Audio")


@patch("headmatch.backend_portaudio._import_sd")
def test_play_and_record_failure(mock_sd_factory, tmp_path):
    mock_sd = MagicMock()
    mock_sd.playrec.side_effect = Exception("Device not available")
    mock_sd.query_devices.side_effect = lambda dev, kind=None: {
        "max_output_channels": 2, "max_input_channels": 2,
    }
    mock_sd_factory.return_value = mock_sd

    from headmatch.signals import SweepSpec
    spec = SweepSpec(sample_rate=48000, duration_s=1.0)
    paths = MeasurementPaths(
        sweep_wav=tmp_path / "sweep.wav",
        recording_wav=tmp_path / "recording.wav",
    )

    backend = PortAudioBackend()
    with pytest.raises(RuntimeError, match="playback/recording failed"):
        backend.play_and_record(spec, paths, DeviceConfig(output_target="0", input_target="1"))


# ── format_device_list ──

def test_format_device_list():
    devices = [
        AudioDevice("playback", "0", "Speakers", "Speakers (2ch out)", {"default_samplerate": 48000}),
        AudioDevice("capture", "1", "Microphone", "Microphone (2ch in)", {"default_samplerate": 44100}),
    ]
    backend = PortAudioBackend()
    text = backend.format_device_list(devices)
    assert "Playback targets" in text
    assert "Speakers -> 0" in text
    assert "Capture targets" in text
    assert "Microphone -> 1" in text


# ── doctor checks ──

@patch("headmatch.backend_portaudio._import_sd")
def test_doctor_checks_healthy(mock_sd_factory):
    mock_sd = MagicMock()
    mock_sd.__version__ = "0.5.0"
    mock_sd.query_devices.return_value = MOCK_DEVICES
    mock_sd_factory.return_value = mock_sd

    backend = PortAudioBackend()
    checks = backend.collect_doctor_checks()
    by_name = {c.name: c for c in checks}
    assert by_name["sounddevice"].ok is True
    assert by_name["audio discovery"].ok is True


@patch("headmatch.backend_portaudio._import_sd")
def test_doctor_checks_no_sounddevice(mock_sd_factory):
    mock_sd_factory.side_effect = RuntimeError("sounddevice not installed")

    backend = PortAudioBackend()
    checks = backend.collect_doctor_checks()
    assert len(checks) == 1
    assert checks[0].ok is False
    assert "sounddevice" in checks[0].name


# ── _import_sd error handling ──

def test_import_sd_missing_library():
    with patch.dict("sys.modules", {"sounddevice": None}):
        # Force re-import to fail
        with pytest.raises(RuntimeError):
            import importlib
            import headmatch.backend_portaudio as mod
            importlib.reload(mod)
            mod._import_sd()
