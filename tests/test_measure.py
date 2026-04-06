from __future__ import annotations

from headmatch.contracts import FrontendConfig
from headmatch.measure import (
    DoctorCheck,
    PipeWireTarget,
    PipeWireTargetSelection,
    collect_pipewire_target_selection,
    _saved_target_matches_discovery,
    collect_doctor_checks,
    format_doctor_report,
    format_pipewire_targets,
)
from headmatch.backend_pipewire import (
    _parse_wpctl_default_ids,
    _parse_wpctl_inspect_node_name,
    _resolve_preferred as _resolve_preferred_pipewire_target,
    _parse_pw_dump as _parse_pipewire_targets,
)


def test_parse_pipewire_targets_keeps_likely_playback_and_capture_nodes():
    payload = [
        {
            "info": {
                "props": {
                    "media.class": "Audio/Sink",
                    "node.name": "alsa_output.usb-dac",
                    "node.description": "USB DAC",
                }
            }
        },
        {
            "info": {
                "props": {
                    "media.class": "Audio/Source",
                    "node.name": "alsa_input.usb-mic",
                    "node.nick": "USB Mic",
                }
            }
        },
        {
            "info": {
                "props": {
                    "media.class": "Stream/Output/Audio",
                    "node.name": "ignored.stream",
                }
            }
        },
    ]

    targets = _parse_pipewire_targets(payload)

    assert [target.kind for target in targets] == ["capture", "playback"]
    assert [target.device_id for target in targets] == ["alsa_input.usb-mic", "alsa_output.usb-dac"]
    assert targets[0].label == "USB Mic"
    assert targets[1].label == "USB DAC"


def test_format_pipewire_targets_groups_entries_for_cli_output():
    text = format_pipewire_targets(
        [
            PipeWireTarget(kind="playback", device_id="alsa_output.usb-dac", label='USB DAC', description="USB DAC", raw_info={'node_name': "alsa_output.usb-dac", 'nick': "", 'media_class': "Audio/Sink"}),
            PipeWireTarget(kind="capture", device_id="alsa_input.usb-mic", label='USB Mic', description="", raw_info={'node_name': "alsa_input.usb-mic", 'nick': "USB Mic", 'media_class': "Audio/Source"}),
        ]
    )

    assert "Playback targets (--output-target)" in text
    assert "USB DAC ->" in text
    assert "alsa_output.usb-dac" in text
    assert "Capture targets (--input-target)" in text
    assert "USB Mic ->" in text
    assert "alsa_input.usb-mic" in text


def test_saved_target_matches_discovery_uses_simple_node_name_matching():
    targets = [
        PipeWireTarget(kind="playback", device_id="alsa_output.usb-dac", label='USB DAC', description="USB DAC", raw_info={'node_name': "alsa_output.usb-dac", 'nick': "", 'media_class': "Audio/Sink"}),
        PipeWireTarget(kind="capture", device_id="alsa_input.usb-mic", label='USB Mic', description="USB Mic", raw_info={'node_name': "alsa_input.usb-mic", 'nick': "", 'media_class': "Audio/Source"}),
    ]

    assert _saved_target_matches_discovery("alsa_output.usb-dac", "playback", targets) is True
    assert _saved_target_matches_discovery("usb-mic", "capture", targets) is True
    assert _saved_target_matches_discovery("usb-mic", "playback", targets) is False
    assert _saved_target_matches_discovery("missing", "capture", targets) is False


def test_collect_doctor_checks_reports_missing_tools_and_targets(tmp_path, monkeypatch):
    monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: None)

    checks = collect_doctor_checks(tmp_path / "config.json", FrontendConfig())

    by_name = {check.name: check for check in checks}
    assert by_name["config file"].ok is False
    assert by_name["pw-dump"].ok is False
    assert by_name["pw-play"].ok is False
    assert by_name["pw-record"].ok is False
    assert by_name["audio discovery"].detail == "Skipped because pw-dump is not available."
    assert by_name["saved output target"].ok is False
    assert by_name["saved input target"].ok is False
    assert by_name["starter sweep settings"].ok is True


def test_collect_doctor_checks_validates_saved_targets_against_discovery(tmp_path, monkeypatch):
    _mock_devices = [
            PipeWireTarget(kind="playback", device_id="alsa_output.usb-dac", label='USB DAC', description="USB DAC", raw_info={'node_name': "alsa_output.usb-dac", 'nick': "", 'media_class': "Audio/Sink"}),
            PipeWireTarget(kind="capture", device_id="alsa_input.usb-mic", label='USB Mic', description="USB Mic", raw_info={'node_name': "alsa_input.usb-mic", 'nick': "", 'media_class': "Audio/Source"}),
        ]
    monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("headmatch.backend_pipewire.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("headmatch.measure.list_pipewire_targets", lambda: _mock_devices)
    # Also patch the backend's discover_devices used by collect_doctor_checks
    monkeypatch.setattr("headmatch.backend_pipewire.PipeWireBackend.discover_devices", lambda self: _mock_devices)

    checks = collect_doctor_checks(
        tmp_path / "config.json",
        FrontendConfig(pipewire_output_target="usb-dac", pipewire_input_target="missing-input"),
    )

    by_name = {check.name: check for check in checks}
    assert by_name["audio discovery"].ok is True
    assert by_name["saved output target"].ok is True
    assert by_name["saved output target"].detail == "Configured and found: usb-dac"
    assert by_name["saved input target"].ok is False
    assert by_name["saved input target"].detail == "Configured but not found now: missing-input"
    assert by_name["saved input target"].action == "Run 'headmatch list-targets' and save an updated --input-target if the device name changed."


def test_format_doctor_report_includes_actions(tmp_path):
    text = format_doctor_report(
        [
            DoctorCheck(name="config file", ok=True, detail="Using config.json"),
            DoctorCheck(name="audio discovery", ok=False, detail="No playback targets found.", action="Connect your DAC and try again."),
        ],
        config_path=tmp_path / "config.json",
    )

    assert "HeadMatch doctor" in text
    assert "Readiness: 1/2 checks look good." in text
    assert "[OK] config file: Using config.json" in text
    assert "[WARN] audio discovery: No playback targets found." in text
    assert "Suggested next steps:" in text
    assert "- audio discovery: Connect your DAC and try again." in text


def test_parse_wpctl_default_ids_reads_starred_sink_and_source_ids():
    status = """Audio
 ├─ Devices:
 │      40. USB Audio Device
 ├─ Sinks:
 │  *   51. USB DAC
 ├─ Sources:
 │  *   61. USB Mic
 └─ Streams:
"""

    defaults = _parse_wpctl_default_ids(status)

    assert defaults == {'playback': 51, 'capture': 61}


def test_parse_wpctl_inspect_node_name_reads_pipewire_node_name():
    inspect = 'id 51, type PipeWire:Interface:Node\n    node.name = "alsa_output.usb-dac"\n'

    assert _parse_wpctl_inspect_node_name(inspect) == 'alsa_output.usb-dac'


def test_get_pipewire_default_targets_returns_empty_when_wpctl_is_missing(monkeypatch):
    monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: None if name == "wpctl" else f"/usr/bin/{name}")

    assert __import__("headmatch.measure", fromlist=["get_pipewire_default_targets"]).get_pipewire_default_targets() == {}


def test_resolve_preferred_pipewire_target_prefers_saved_then_default_then_first():
    targets = [
        PipeWireTarget(kind='playback', device_id='alsa_output.hdmi', label='HDMI', description='HDMI', raw_info={'node_name': 'alsa_output.hdmi', 'nick': '', 'media_class': 'Audio/Sink'}),
        PipeWireTarget(kind='playback', device_id='alsa_output.usb-dac', label='USB DAC', description='USB DAC', raw_info={'node_name': 'alsa_output.usb-dac', 'nick': '', 'media_class': 'Audio/Sink'}),
    ]

    assert _resolve_preferred_pipewire_target('playback', 'usb-dac', targets, 'alsa_output.hdmi') == 'alsa_output.usb-dac'
    assert _resolve_preferred_pipewire_target('playback', None, targets, 'alsa_output.hdmi') == 'alsa_output.hdmi'
    assert _resolve_preferred_pipewire_target('playback', None, targets, 'missing') == 'alsa_output.hdmi'
    assert _resolve_preferred_pipewire_target('capture', None, targets, None) == ''


def test_collect_pipewire_target_selection_uses_discovery_and_defaults(monkeypatch):
    _mock_devices = [
        PipeWireTarget(kind='playback', device_id='alsa_output.hdmi', label='HDMI', description='HDMI', raw_info={'node_name': 'alsa_output.hdmi', 'nick': '', 'media_class': 'Audio/Sink'}),
        PipeWireTarget(kind='playback', device_id='alsa_output.usb-dac', label='USB DAC', description='USB DAC', raw_info={'node_name': 'alsa_output.usb-dac', 'nick': '', 'media_class': 'Audio/Sink'}),
        PipeWireTarget(kind='capture', device_id='alsa_input.usb-mic', label='USB Mic', description='USB Mic', raw_info={'node_name': 'alsa_input.usb-mic', 'nick': '', 'media_class': 'Audio/Source'}),
    ]
    monkeypatch.setattr('headmatch.backend_pipewire.PipeWireBackend.discover_devices', lambda self: _mock_devices)
    monkeypatch.setattr('headmatch.backend_pipewire.PipeWireBackend.get_default_devices', lambda self: {'playback': 'alsa_output.hdmi', 'capture': 'alsa_input.usb-mic'})

    selection = collect_pipewire_target_selection(FrontendConfig(pipewire_output_target='usb-dac'))

    assert isinstance(selection, PipeWireTargetSelection)
    assert [target.device_id for target in selection.playback_targets] == ['alsa_output.hdmi', 'alsa_output.usb-dac']
    assert [target.device_id for target in selection.capture_targets] == ['alsa_input.usb-mic']
    assert selection.selected_playback == 'alsa_output.usb-dac'
    assert selection.selected_capture == 'alsa_input.usb-mic'
