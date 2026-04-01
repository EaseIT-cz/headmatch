from __future__ import annotations

import pytest

from headmatch import cli


@pytest.mark.parametrize(
    ('cmd', 'message', 'expected'),
    [
        (
            'clone-target',
            'Output CSV must not overwrite the source or target measurement file',
            'Check that both input CSVs include frequency and response columns',
        ),
        (
            'fit',
            'Target curve must span 1 kHz for normalization. Got 20.0 Hz to 900.0 Hz.',
            'Use a target file that includes frequency + response data and spans 1 kHz.',
        ),
        (
            'fit-offline',
            'Could not find a frequency column in bad.csv. Supported names include frequency_hz, frequency, freq, freq_hz, or hz.',
            'Expected a CSV with a frequency column such as frequency_hz/frequency/freq',
        ),
    ],
)
def test_format_user_error_adds_beginner_friendly_hints(cmd, message, expected):
    formatted = cli.format_user_error(cmd, ValueError(message))
    assert message in formatted
    assert expected in formatted
