from __future__ import annotations

from headmatch.contracts import FrontendConfig
from headmatch.measure import (
    DoctorCheck,
    PipeWireTarget,
    PipeWireTargetSelection,
    _parse_wpctl_default_ids,
    _parse_wpctl_inspect_node_name,
    _resolve_preferred_pipewire_target,
    collect_pipewire_target_selection,
    _parse_pipewire_targets,
    _saved_target_matches_discovery,
    collect_doctor_checks,
    format_doctor_report,
    format_pipewire_targets,
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
    assert [target.node_name for target in targets] == ["alsa_input.usb-mic", "alsa_output.usb-dac"]
    assert targets[0].label == "USB Mic"
    assert targets[1].label == "USB DAC"


def test_format_pipewire_targets_groups_entries_for_cli_output():
    text = format_pipewire_targets(
        [
            PipeWireTarget("playback", "alsa_output.usb-dac", "USB DAC", "", "Audio/Sink"),
            PipeWireTarget("capture", "alsa_input.usb-mic", "", "USB Mic", "Audio/Source"),
        ]
    )

    assert "Playback targets (--output-target)" in text
    assert "Choose the DAC, headphones, speakers, or interface output" in text
    assert "USB DAC -> alsa_output.usb-dac [Audio/Sink]" in text
    assert "Capture targets (--input-target)" in text
    assert "Choose the mic, recorder, or interface input connected to your measurement rig." in text
    assert "USB Mic -> alsa_input.usb-mic [Audio/Source]" in text
    assert "Avoid monitor/loopback-style entries" in text
    assert "copy the exact node.name values first" in text


def test_saved_target_matches_discovery_uses_simple_node_name_matching():
    targets = [
        PipeWireTarget("playback", "alsa_output.usb-dac", "USB DAC", "", "Audio/Sink"),
        PipeWireTarget("capture", "alsa_input.usb-mic", "USB Mic", "", "Audio/Source"),
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
    assert by_name["PipeWire discovery"].detail == "Skipped because pw-dump is not available."
    assert by_name["saved output target"].ok is False
    assert by_name["saved input target"].ok is False
    assert by_name["starter sweep settings"].ok is True


def test_collect_doctor_checks_validates_saved_targets_against_discovery(tmp_path, monkeypatch):
    monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "headmatch.measure.list_pipewire_targets",
        lambda: [
            PipeWireTarget("playback", "alsa_output.usb-dac", "USB DAC", "", "Audio/Sink"),
            PipeWireTarget("capture", "alsa_input.usb-mic", "USB Mic", "", "Audio/Source"),
        ],
    )

    checks = collect_doctor_checks(
        tmp_path / "config.json",
        FrontendConfig(pipewire_output_target="usb-dac", pipewire_input_target="missing-input"),
    )

    by_name = {check.name: check for check in checks}
    assert by_name["PipeWire discovery"].ok is True
    assert by_name["saved output target"].ok is True
    assert by_name["saved output target"].detail == "Configured and found: usb-dac"
    assert by_name["saved input target"].ok is False
    assert by_name["saved input target"].detail == "Configured but not found now: missing-input"
    assert by_name["saved input target"].action == "Run 'headmatch list-targets' and save an updated --input-target if the device name changed."


def test_format_doctor_report_includes_actions(tmp_path):
    text = format_doctor_report(
        [
            DoctorCheck(name="config file", ok=True, detail="Using config.json"),
            DoctorCheck(name="PipeWire discovery", ok=False, detail="No playback targets found.", action="Connect your DAC and try again."),
        ],
        config_path=tmp_path / "config.json",
    )

    assert "HeadMatch doctor" in text
    assert "Readiness: 1/2 checks look good." in text
    assert "[OK] config file: Using config.json" in text
    assert "[WARN] PipeWire discovery: No playback targets found." in text
    assert "Suggested next steps:" in text
    assert "- PipeWire discovery: Connect your DAC and try again." in text


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


def test_resolve_preferred_pipewire_target_prefers_saved_then_default_then_first():
    targets = [
        PipeWireTarget('playback', 'alsa_output.hdmi', 'HDMI', '', 'Audio/Sink'),
        PipeWireTarget('playback', 'alsa_output.usb-dac', 'USB DAC', '', 'Audio/Sink'),
    ]

    assert _resolve_preferred_pipewire_target('playback', 'usb-dac', targets, 'alsa_output.hdmi') == 'alsa_output.usb-dac'
    assert _resolve_preferred_pipewire_target('playback', None, targets, 'alsa_output.hdmi') == 'alsa_output.hdmi'
    assert _resolve_preferred_pipewire_target('playback', None, targets, 'missing') == 'alsa_output.hdmi'
    assert _resolve_preferred_pipewire_target('capture', None, targets, None) == ''


def test_collect_pipewire_target_selection_uses_discovery_and_defaults(monkeypatch):
    monkeypatch.setattr(
        'headmatch.measure.list_pipewire_targets',
        lambda: [
            PipeWireTarget('playback', 'alsa_output.hdmi', 'HDMI', '', 'Audio/Sink'),
            PipeWireTarget('playback', 'alsa_output.usb-dac', 'USB DAC', '', 'Audio/Sink'),
            PipeWireTarget('capture', 'alsa_input.usb-mic', 'USB Mic', '', 'Audio/Source'),
        ],
    )
    monkeypatch.setattr('headmatch.measure.get_pipewire_default_targets', lambda: {'playback': 'alsa_output.hdmi', 'capture': 'alsa_input.usb-mic'})

    selection = collect_pipewire_target_selection(FrontendConfig(pipewire_output_target='usb-dac'))

    assert isinstance(selection, PipeWireTargetSelection)
    assert [target.node_name for target in selection.playback_targets] == ['alsa_output.hdmi', 'alsa_output.usb-dac']
    assert [target.node_name for target in selection.capture_targets] == ['alsa_input.usb-mic']
    assert selection.selected_playback == 'alsa_output.usb-dac'
    assert selection.selected_capture == 'alsa_input.usb-mic'
