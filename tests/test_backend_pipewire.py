"""Direct tests for PipeWire audio backend.

Ensures the backend_pipewire module works correctly independent
of the measure.py wrapper layer.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from headmatch.audio_backend import AudioDevice, DeviceConfig, MeasurementPaths
from headmatch.backend_pipewire import (
    PipeWireBackend,
    _parse_pw_dump,
    _parse_wpctl_default_ids,
    _parse_wpctl_inspect_node_name,
    _resolve_preferred,
    _classify_media_class,
)


# ── Classification ──

def test_classify_sink():
    assert _classify_media_class("Audio/Sink") == "playback"

def test_classify_sink_subtype():
    assert _classify_media_class("Audio/Sink/Virtual") == "playback"

def test_classify_source():
    assert _classify_media_class("Audio/Source") == "capture"

def test_classify_stream_ignored():
    assert _classify_media_class("Stream/Output/Audio") is None

def test_classify_empty():
    assert _classify_media_class("") is None


# ── pw-dump parsing ──

PW_DUMP_PAYLOAD = [
    {"info": {"props": {"media.class": "Audio/Sink", "node.name": "alsa_output.usb-dac",
                         "node.description": "USB DAC", "node.nick": ""}}},
    {"info": {"props": {"media.class": "Audio/Source", "node.name": "alsa_input.usb-mic",
                         "node.description": "", "node.nick": "USB Mic"}}},
    {"info": {"props": {"media.class": "Stream/Output/Audio", "node.name": "ignored"}}},
    {"not_a_device": True},
    {"info": "not_a_dict"},
    {"info": {"props": {"media.class": "Audio/Sink", "node.name": ""}}},  # empty name
]


def test_parse_pw_dump_extracts_devices():
    devices = _parse_pw_dump(PW_DUMP_PAYLOAD)
    assert len(devices) == 2
    kinds = {d.kind for d in devices}
    assert kinds == {"playback", "capture"}


def test_parse_pw_dump_device_ids():
    devices = _parse_pw_dump(PW_DUMP_PAYLOAD)
    ids = {d.device_id for d in devices}
    assert "alsa_output.usb-dac" in ids
    assert "alsa_input.usb-mic" in ids


def test_parse_pw_dump_labels():
    devices = _parse_pw_dump(PW_DUMP_PAYLOAD)
    by_id = {d.device_id: d for d in devices}
    assert by_id["alsa_output.usb-dac"].label == "USB DAC"
    assert by_id["alsa_input.usb-mic"].label == "USB Mic"  # falls back to nick


def test_parse_pw_dump_deduplicates():
    payload = [
        {"info": {"props": {"media.class": "Audio/Sink", "node.name": "dac",
                             "node.description": "DAC", "node.nick": ""}}},
        {"info": {"props": {"media.class": "Audio/Sink", "node.name": "dac",
                             "node.description": "DAC v2", "node.nick": ""}}},
    ]
    devices = _parse_pw_dump(payload)
    assert len(devices) == 1


def test_parse_pw_dump_raw_info():
    devices = _parse_pw_dump(PW_DUMP_PAYLOAD)
    dac = next(d for d in devices if d.device_id == "alsa_output.usb-dac")
    assert dac.raw_info["node_name"] == "alsa_output.usb-dac"
    assert dac.raw_info["media_class"] == "Audio/Sink"


# ── wpctl parsing ──

WPCTL_STATUS = """
PipeWire 'pipewire-0' [1.0.0]
 └─ Clients:
        31. PipeWire                            [1.0.0, user]

Audio
 ├─ Devices:
 │      40. USB DAC                             [alsa]
 ├─ Sinks:
 │      41. USB DAC / Analog Stereo
 │    * 42. Built-in Audio Analog Stereo
 ├─ Sources:
 │    * 51. USB Mic
 │      52. Monitor of Built-in Audio
 ├─ Streams:
"""


def test_parse_wpctl_default_ids():
    ids = _parse_wpctl_default_ids(WPCTL_STATUS)
    assert ids["playback"] == 42
    assert ids["capture"] == 51


def test_parse_wpctl_inspect_node_name():
    inspect = '  * node.name = "alsa_output.usb-dac"\n    media.class = "Audio/Sink"'
    assert _parse_wpctl_inspect_node_name(inspect) == "alsa_output.usb-dac"


def test_parse_wpctl_inspect_no_match():
    assert _parse_wpctl_inspect_node_name("no relevant data") is None


# ── Target resolution ──

def test_resolve_preferred_saved_substring():
    devices = [
        AudioDevice("playback", "alsa_output.hdmi", "HDMI", "", {}),
        AudioDevice("playback", "alsa_output.usb-dac", "USB DAC", "", {}),
    ]
    assert _resolve_preferred("playback", "usb-dac", devices, "alsa_output.hdmi") == "alsa_output.usb-dac"


def test_resolve_preferred_default():
    devices = [
        AudioDevice("playback", "alsa_output.hdmi", "HDMI", "", {}),
        AudioDevice("playback", "alsa_output.usb-dac", "USB DAC", "", {}),
    ]
    assert _resolve_preferred("playback", None, devices, "alsa_output.usb-dac") == "alsa_output.usb-dac"


def test_resolve_preferred_first_fallback():
    devices = [
        AudioDevice("playback", "alsa_output.hdmi", "HDMI", "", {}),
    ]
    assert _resolve_preferred("playback", None, devices, "missing") == "alsa_output.hdmi"


def test_resolve_preferred_empty_kind():
    devices = [AudioDevice("playback", "out", "Out", "", {})]
    assert _resolve_preferred("capture", None, devices, None) == ""


# ── Backend.discover_devices (mocked subprocess) ──

@patch("headmatch.backend_pipewire.shutil.which", return_value="/usr/bin/pw-dump")
@patch("headmatch.backend_pipewire._run_discovery")
def test_backend_discover_devices(mock_run, mock_which):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(PW_DUMP_PAYLOAD),
    )
    backend = PipeWireBackend()
    devices = backend.discover_devices()
    assert len(devices) == 2
    mock_run.assert_called_once_with(["pw-dump"])


@patch("headmatch.backend_pipewire.shutil.which", return_value=None)
def test_backend_discover_devices_no_pw_dump(mock_which):
    backend = PipeWireBackend()
    with pytest.raises(RuntimeError, match="pw-dump"):
        backend.discover_devices()


@patch("headmatch.backend_pipewire.shutil.which", return_value="/usr/bin/pw-dump")
@patch("headmatch.backend_pipewire._run_discovery")
def test_backend_discover_devices_bad_json(mock_run, mock_which):
    mock_run.return_value = MagicMock(returncode=0, stdout="not json")
    backend = PipeWireBackend()
    with pytest.raises(RuntimeError, match="invalid JSON"):
        backend.discover_devices()


# ── Backend.get_default_devices (mocked subprocess) ──

@patch("headmatch.backend_pipewire.shutil.which", return_value="/usr/bin/wpctl")
@patch("headmatch.backend_pipewire._run_discovery")
def test_backend_get_defaults(mock_run, mock_which):
    def side_effect(cmd):
        if cmd == ["wpctl", "status"]:
            return MagicMock(returncode=0, stdout=WPCTL_STATUS)
        if cmd[0] == "wpctl" and cmd[1] == "inspect":
            obj_id = cmd[2]
            names = {"42": "alsa_output.builtin", "51": "alsa_input.usb-mic"}
            name = names.get(obj_id, "unknown")
            return MagicMock(returncode=0, stdout=f'node.name = "{name}"')
        return MagicMock(returncode=1)
    mock_run.side_effect = side_effect

    backend = PipeWireBackend()
    defaults = backend.get_default_devices()
    assert defaults["playback"] == "alsa_output.builtin"
    assert defaults["capture"] == "alsa_input.usb-mic"


@patch("headmatch.backend_pipewire.shutil.which", return_value=None)
def test_backend_get_defaults_no_wpctl(mock_which):
    backend = PipeWireBackend()
    assert backend.get_default_devices() == {}


# ── Backend.collect_doctor_checks ──

@patch("headmatch.backend_pipewire.shutil.which", return_value=None)
def test_backend_doctor_no_tools(mock_which):
    backend = PipeWireBackend()
    checks = backend.collect_doctor_checks()
    by_name = {c.name: c for c in checks}
    assert by_name["pw-dump"].ok is False
    assert by_name["pw-play"].ok is False
    assert by_name["pw-record"].ok is False
    assert by_name["audio discovery"].ok is False


@patch("headmatch.backend_pipewire.shutil.which", return_value="/usr/bin/pw-dump")
@patch("headmatch.backend_pipewire.PipeWireBackend.discover_devices")
def test_backend_doctor_with_devices(mock_discover, mock_which):
    mock_discover.return_value = [
        AudioDevice("playback", "out", "Out", "", {}),
        AudioDevice("capture", "in", "In", "", {}),
    ]
    backend = PipeWireBackend()
    checks = backend.collect_doctor_checks()
    by_name = {c.name: c for c in checks}
    assert by_name["audio discovery"].ok is True
    assert "1 playback" in by_name["audio discovery"].detail


# ── Backend.format_device_list ──

def test_backend_format_device_list():
    devices = [
        AudioDevice("playback", "alsa_output.usb-dac", "USB DAC", "", {"node_name": "alsa_output.usb-dac", "nick": "", "media_class": "Audio/Sink"}),
        AudioDevice("capture", "alsa_input.usb-mic", "USB Mic", "", {"node_name": "alsa_input.usb-mic", "nick": "", "media_class": "Audio/Source"}),
    ]
    backend = PipeWireBackend()
    text = backend.format_device_list(devices)
    assert "Playback targets" in text
    assert "USB DAC -> alsa_output.usb-dac" in text
    assert "Capture targets" in text
    assert "USB Mic -> alsa_input.usb-mic" in text
