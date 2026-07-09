"""Smoke tests for plots.py — verify SVG generation doesn't crash and produces valid output."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from headmatch.analysis import MeasurementResult
from headmatch.peq import PEQBand
from headmatch.plots import (
    render_fit_graphs,
    _cutoff_x_position,
    _cutoff_region_svg,
)
from headmatch.targets import create_flat_target


def _dummy_result() -> MeasurementResult:
    freqs = np.geomspace(20, 20000, 480)
    flat = np.zeros_like(freqs)
    noise = np.random.RandomState(42).randn(len(freqs)) * 2
    return MeasurementResult(
        freqs_hz=freqs,
        left_db=flat + noise,
        right_db=flat - noise,
        left_raw_db=flat + noise * 1.5,
        right_raw_db=flat - noise * 1.5,
        diagnostics={},
    )


def test_render_fit_graphs_produces_valid_svg_files(tmp_path: Path):
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    bands_left = [PEQBand("peaking", 1000.0, -3.0, 1.4)]
    bands_right = [PEQBand("peaking", 4000.0, 2.0, 2.0)]
    paths = render_fit_graphs(tmp_path, result, target, 48000, bands_left, bands_right)
    assert set(paths.keys()) == {"overview", "left", "right"}
    for key, svg_path in paths.items():
        p = Path(svg_path)
        assert p.exists(), f"{key} SVG not created"
        content = p.read_text()
        assert content.startswith("<?xml") or content.startswith("<svg"), f"{key} SVG has invalid header"
        assert "</svg>" in content, f"{key} SVG is not closed"
        assert len(content) > 500, f"{key} SVG is suspiciously small"


def test_render_fit_graphs_handles_empty_bands(tmp_path: Path):
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    paths = render_fit_graphs(tmp_path, result, target, 48000, [], [])
    for key, svg_path in paths.items():
        assert Path(svg_path).exists()


def test_render_fit_graphs_handles_shelf_bands(tmp_path: Path):
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    bands = [
        PEQBand("lowshelf", 100.0, 4.0, 0.7),
        PEQBand("highshelf", 8000.0, -2.0, 0.7),
        PEQBand("peaking", 3000.0, -5.0, 2.0),
    ]
    paths = render_fit_graphs(tmp_path, result, target, 48000, bands, bands)
    for svg_path in paths.values():
        assert Path(svg_path).exists()


def test_render_fit_graphs_without_cutoff_hz_matches_baseline(tmp_path: Path):
    """Default behavior (cutoff_hz=None) preserves current graph output exactly."""
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    bands_left = [PEQBand("peaking", 1000.0, -3.0, 1.4)]
    bands_right = [PEQBand("peaking", 4000.0, 2.0, 2.0)]

    # Run without cutoff_hz
    paths1 = render_fit_graphs(tmp_path / "baseline", result, target, 48000, bands_left, bands_right)
    # Run with explicit cutoff_hz=None
    paths2 = render_fit_graphs(tmp_path / "explicit", result, target, 48000, bands_left, bands_right, cutoff_hz=None)

    for key in ["overview", "left", "right"]:
        content1 = Path(paths1[key]).read_text()
        content2 = Path(paths2[key]).read_text()
        assert content1 == content2, f"Content mismatch for {key}"


def test_render_fit_graphs_with_cutoff_hz_produces_marker(tmp_path: Path):
    """cutoff_hz param displays vertical line and shaded region."""
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    bands_left = [PEQBand("peaking", 1000.0, -3.0, 1.4)]
    bands_right = [PEQBand("peaking", 4000.0, 2.0, 2.0)]
    cutoff = 8000.0

    paths = render_fit_graphs(tmp_path, result, target, 48000, bands_left, bands_right, cutoff_hz=cutoff)

    for key, svg_path in paths.items():
        content = Path(svg_path).read_text()
        # Check for shaded region (grey fill)
        assert 'fill="#f3f4f6"' in content, f"Shaded region not found in {key}"
        # Check for vertical line at cutoff
        assert 'stroke-dasharray="3 3"' in content, f"Cutoff marker not found in {key}"
        # Verify the file is still valid SVG
        assert content.startswith("<?xml") or content.startswith("<svg")
        assert "</svg>" in content


def test_cutoff_x_position_calculation():
    """Unit test for _cutoff_x_position helper."""
    freqs = np.geomspace(20, 20000, 100)
    width = 1000.0

    # Cutoff at geometric center should give roughly half width
    mid = 1000.0
    pos_mid = _cutoff_x_position(mid, freqs, width)
    assert pos_mid is not None
    assert 400 < pos_mid < 600  # Roughly centered

    # Cutoff below range returns None
    assert _cutoff_x_position(10.0, freqs, width) is None

    # Cutoff above range returns None
    assert _cutoff_x_position(30000.0, freqs, width) is None



def test_cutoff_region_svg_produces_expected_elements():
    """Unit test for _cutoff_region_svg helper."""
    elements = _cutoff_region_svg(500.0, 70.0, 80.0, 1030.0, 250.0)
    assert len(elements) == 2

    # First element should be the shaded rect
    assert 'fill="#f3f4f6"' in elements[0]
    assert 'x="570.00"' in elements[0]  # 70 + 500

    # Second element should be the vertical line
    assert 'x1="570.00"' in elements[1]
    assert 'stroke-dasharray="3 3"' in elements[1]


def test_render_fit_graphs_with_cutoff_at_freq_boundaries(tmp_path: Path):
    """Edge case: cutoff_hz at or near frequency boundaries."""
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)
    freqs = result.freqs_hz

    # Test cutoff at exactly the min frequency
    paths_low = render_fit_graphs(
        tmp_path / "low",
        result,
        target,
        48000,
        [],
        [],
        cutoff_hz=float(freqs[0]),
    )
    # Should still work without error
    for svg_path in paths_low.values():
        assert Path(svg_path).exists()

    # Test cutoff at exactly the max frequency
    paths_high = render_fit_graphs(
        tmp_path / "high",
        result,
        target,
        48000,
        [],
        [],
        cutoff_hz=float(freqs[-1]),
    )
    # Should still work without error
    for svg_path in paths_high.values():
        assert Path(svg_path).exists()



def test_render_fit_graphs_with_cutoff_below_range(tmp_path: Path):
    """Edge case: cutoff_hz below min frequency should not crash."""
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)

    paths = render_fit_graphs(
        tmp_path,
        result,
        target,
        48000,
        [],
        [],
        cutoff_hz=10.0,  # Below min freq (~20Hz)
    )
    for svg_path in paths.values():
        content = Path(svg_path).read_text()
        # No marker should appear since cutoff is out of range
        assert 'fill="#f3f4f6"' not in content
        assert Path(svg_path).exists()


def test_render_fit_graphs_with_cutoff_above_range(tmp_path: Path):
    """Edge case: cutoff_hz above max frequency should not crash."""
    result = _dummy_result()
    target = create_flat_target(result.freqs_hz)

    paths = render_fit_graphs(
        tmp_path,
        result,
        target,
        48000,
        [],
        [],
        cutoff_hz=30000.0,  # Above max freq (~20000Hz)
    )
    for svg_path in paths.values():
        content = Path(svg_path).read_text()
        # No marker should appear since cutoff is out of range
        assert 'fill="#f3f4f6"' not in content
        assert Path(svg_path).exists()