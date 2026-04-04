"""Smoke tests for plots.py — verify SVG generation doesn't crash and produces valid output."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from headmatch.analysis import MeasurementResult
from headmatch.peq import PEQBand
from headmatch.plots import render_fit_graphs
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
