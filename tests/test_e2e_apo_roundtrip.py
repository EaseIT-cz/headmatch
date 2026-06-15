"""End-to-end test for the import-apo -> refine-apo inter-command contract.

An Equalizer APO parametric preset that is imported and then refined against a
synthetic measurement must still produce a valid APO preset that re-parses
cleanly through the real importer into a non-empty band list.

All assertions use the production APO parser (``parse_apo_parametric`` /
``load_apo_preset``) rather than hand-rolled regex so they exercise the real
round-trip contract.
"""
from __future__ import annotations

from pathlib import Path

from headmatch import cli
from headmatch.apo_import import load_apo_preset, parse_apo_parametric

from tests.test_integration_cli import (
    _patch_cli_config,
    _read_json,
    build_synthetic_recording,
)


# Bands we hand-write into the source preset. Frequencies, gains and Qs are
# chosen so they survive the importer's "%.1f Hz / %.1f dB / %.2f Q" round-trip
# without rounding surprises.
_LEFT_SPEC = [
    # (kind_token, fc_hz, gain_db, q)
    ("PK", 120.0, -3.0, 1.00),
    ("PK", 2500.0, 4.5, 1.40),
    ("PK", 8000.0, -2.5, 2.80),
]
_RIGHT_SPEC = [
    ("PK", 110.0, -2.0, 0.90),
    ("PK", 3000.0, 5.0, 1.60),
    ("PK", 9000.0, -3.0, 3.00),
]


def _write_source_preset(path: Path) -> Path:
    """Write a known stereo parametric APO preset matching the importer format."""
    lines = ["; e2e source preset"]
    for label, spec in [("Channel: L", _LEFT_SPEC), ("Channel: R", _RIGHT_SPEC)]:
        lines.append(label)
        lines.append("Preamp: 0.0 dB")
        for i, (kind, fc, gain, q) in enumerate(spec, start=1):
            lines.append(
                f"Filter {i}: ON {kind} Fc {fc:.1f} Hz Gain {gain:.1f} dB Q {q:.2f}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_source_preset_parses_to_expected_bands(tmp_path: Path):
    """Sanity: the hand-written preset matches what the real importer expects.

    Contract: the .txt format we author is exactly the format
    ``parse_apo_parametric`` reads, so the bands round-trip to the freqs/gains
    we wrote.
    """
    preset = _write_source_preset(tmp_path / "source.txt")
    left, right = load_apo_preset(preset)

    assert len(left) == len(_LEFT_SPEC)
    assert len(right) == len(_RIGHT_SPEC)
    for band, (_, fc, gain, q) in zip(left, _LEFT_SPEC):
        assert band.kind == "peaking"
        assert band.freq == fc
        assert band.gain_db == gain
        assert band.q == q
    for band, (_, fc, gain, q) in zip(right, _RIGHT_SPEC):
        assert band.kind == "peaking"
        assert band.freq == fc
        assert band.gain_db == gain
        assert band.q == q


def test_import_then_refine_apo_roundtrip(monkeypatch, tmp_path: Path):
    """import-apo -> refine-apo inter-command contract.

    1. import-apo converts the source preset; the emitted equalizer_apo.txt
       re-parses to the same gains/freqs we authored (lossless import).
    2. refine-apo, fed the SAME source preset plus a synthetic measurement,
       emits its own equalizer_apo.txt that re-parses cleanly through the real
       importer into a non-empty stereo band list -- the round-trip contract
       the two commands must jointly uphold.
    """
    _patch_cli_config(monkeypatch, tmp_path)
    preset = _write_source_preset(tmp_path / "source.txt")

    # --- Step 1: import-apo -------------------------------------------------
    imp_dir = tmp_path / "imported"
    cli.main(["import-apo", "--preset", str(preset), "--out-dir", str(imp_dir)])

    # Converted artifacts written by the import-apo handler.
    imported_apo = imp_dir / "equalizer_apo.txt"
    assert imported_apo.exists()
    assert (imp_dir / "camilladsp_full.yaml").exists()
    assert (imp_dir / "camilladsp_filters_only.yaml").exists()

    # Imported bands round-trip back to what we authored, via the real parser.
    imp_left, imp_right = load_apo_preset(imported_apo)
    assert len(imp_left) == len(_LEFT_SPEC)
    assert len(imp_right) == len(_RIGHT_SPEC)
    for band, (_, fc, gain, q) in zip(imp_left, _LEFT_SPEC):
        assert band.kind == "peaking"
        assert band.freq == fc
        assert band.gain_db == gain
        assert band.q == q
    for band, (_, fc, gain, q) in zip(imp_right, _RIGHT_SPEC):
        assert band.freq == fc
        assert band.gain_db == gain
        assert band.q == q

    # --- Step 2: refine-apo against a synthetic measurement -----------------
    recording, spec = build_synthetic_recording(tmp_path)
    ref_dir = tmp_path / "refined"
    cli.main(
        [
            "refine-apo",
            "--preset",
            str(preset),
            "--recording",
            str(recording),
            "--out-dir",
            str(ref_dir),
            "--sample-rate",
            str(spec.sample_rate),
            "--duration",
            str(spec.duration_s),
            "--pre-silence",
            str(spec.pre_silence_s),
            "--post-silence",
            str(spec.post_silence_s),
            "--amplitude",
            str(spec.amplitude),
        ]
    )

    # Refine artifacts produced by refine_apo_preset.
    refined_apo = ref_dir / "equalizer_apo.txt"
    assert refined_apo.exists()
    assert (ref_dir / "camilladsp_full.yaml").exists()
    assert (ref_dir / "fit_overview.svg").exists()

    summary = _read_json(ref_dir / "run_summary.json")
    report = _read_json(ref_dir / "fit_report.json")
    assert report["mode"] == "refine"
    assert report["left_bands"], "refine produced no left bands"
    assert report["right_bands"], "refine produced no right bands"

    # --- The round-trip contract: refined preset re-parses cleanly ----------
    ref_left, ref_right = parse_apo_parametric(refined_apo.read_text(encoding="utf-8"))
    assert ref_left, "refined equalizer_apo.txt re-parsed to an empty left chain"
    assert ref_right, "refined equalizer_apo.txt re-parsed to an empty right chain"

    # The re-parsed text must agree with the structured report the command
    # wrote: same number of bands per channel, all valid PEQ types.
    assert len(ref_left) == len(report["left_bands"])
    assert len(ref_right) == len(report["right_bands"])
    for band in ref_left + ref_right:
        assert band.kind in ("peaking", "lowshelf", "highshelf")
        assert band.freq > 0
        assert band.q > 0
