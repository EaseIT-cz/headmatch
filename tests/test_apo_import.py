"""Tests for APO parametric preset import."""
from __future__ import annotations

from headmatch.apo_import import parse_apo_parametric, load_apo_preset
from pathlib import Path


SAMPLE_STEREO_PRESET = """\
; AutoEQ export
Channel: L
Preamp: -3.50 dB
Filter 1: ON PK Fc 100.00 Hz Gain -3.50 dB Q 1.41
Filter 2: ON LS Fc 50.00 Hz Gain 2.00 dB Q 0.70
Filter 3: ON PK Fc 3000.00 Hz Gain -5.20 dB Q 2.50

Channel: R
Preamp: -2.00 dB
Filter 1: ON PK Fc 200.00 Hz Gain -2.00 dB Q 1.00
Filter 2: ON HS Fc 8000.00 Hz Gain 1.50 dB Q 0.70
"""

SAMPLE_MONO_PRESET = """\
Preamp: -4.00 dB
Filter 1: ON PK Fc 1000.00 Hz Gain -4.00 dB Q 1.41
Filter 2: ON PK Fc 5000.00 Hz Gain 2.00 dB Q 3.00
"""


def test_parse_stereo_preset():
    left, right = parse_apo_parametric(SAMPLE_STEREO_PRESET)
    assert len(left) == 3
    assert len(right) == 2
    assert left[0].kind == "peaking"
    assert left[0].freq == 100.0
    assert left[1].kind == "lowshelf"
    assert right[1].kind == "highshelf"


def test_parse_mono_preset_duplicates_to_both():
    left, right = parse_apo_parametric(SAMPLE_MONO_PRESET)
    assert len(left) == 2
    assert len(right) == 2
    assert left[0].freq == right[0].freq
    assert left[1].gain_db == right[1].gain_db


def test_parse_empty_preset():
    left, right = parse_apo_parametric("")
    assert left == []
    assert right == []


def test_parse_comments_and_blank_lines():
    text = "; comment\n\n; another\nFilter 1: ON PK Fc 500.00 Hz Gain -1.00 dB Q 2.00\n"
    left, right = parse_apo_parametric(text)
    assert len(left) == 1
    assert left[0].freq == 500.0


def test_load_apo_preset_from_file(tmp_path: Path):
    p = tmp_path / "test.txt"
    p.write_text(SAMPLE_STEREO_PRESET)
    left, right = load_apo_preset(p)
    assert len(left) == 3
    assert len(right) == 2


def test_parse_handles_variant_type_names():
    text = "Filter 1: ON PEAKING Fc 100.00 Hz Gain 1.00 dB Q 1.00\nFilter 2: ON LSC Fc 50.00 Hz Gain -2.00 dB Q 0.70\nFilter 3: ON HSC Fc 8000.00 Hz Gain 3.00 dB Q 0.70\n"
    left, right = parse_apo_parametric(text)
    assert len(left) == 3
    assert left[0].kind == "peaking"
    assert left[1].kind == "lowshelf"
    assert left[2].kind == "highshelf"
