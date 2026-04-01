from __future__ import annotations

from headmatch.measure import PipeWireTarget, _parse_pipewire_targets, format_pipewire_targets


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
