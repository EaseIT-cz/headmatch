from __future__ import annotations

from headmatch.contracts import FrontendConfig
from headmatch.measure import (
    DoctorCheck,
    PipeWireTarget,
    _parse_pipewire_targets,
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
