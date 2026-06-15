"""Coverage tests for headmatch.apo_import edge branches."""
from __future__ import annotations

from headmatch.apo_import import parse_apo_parametric


class TestChannelMarkerFallback:
    def test_unknown_channel_marker_falls_back_to_both(self):
        """A Channel marker that is neither L nor R resets to 'both' (line 58),
        so subsequent filters land in both channels."""
        text = (
            "Channel: C\n"
            "Filter 1: ON PK Fc 1000.00 Hz Gain -2.00 dB Q 1.00\n"
        )
        left, right = parse_apo_parametric(text)
        assert len(left) == 1
        assert len(right) == 1
        assert left[0].freq == 1000.0
        assert right[0].freq == 1000.0

    def test_unknown_channel_after_left_resets_to_both(self):
        """An unknown channel marker resets a previously-set channel back to both."""
        text = (
            "Channel: L\n"
            "Filter 1: ON PK Fc 100.00 Hz Gain 1.00 dB Q 1.00\n"
            "Channel: X\n"
            "Filter 2: ON PK Fc 200.00 Hz Gain 1.00 dB Q 1.00\n"
        )
        left, right = parse_apo_parametric(text)
        # First filter: left only. Second filter: both.
        assert [b.freq for b in left] == [100.0, 200.0]
        assert [b.freq for b in right] == [200.0]


class TestUnknownFilterType:
    def test_unrecognized_filter_type_is_skipped(self):
        """A filter line whose type is not in the type map is skipped (line 69)."""
        text = (
            "Filter 1: ON XX Fc 1000.00 Hz Gain -2.00 dB Q 1.00\n"
            "Filter 2: ON PK Fc 2000.00 Hz Gain -1.00 dB Q 1.00\n"
        )
        left, right = parse_apo_parametric(text)
        # Only the recognized PK filter should survive.
        assert len(left) == 1
        assert left[0].freq == 2000.0
