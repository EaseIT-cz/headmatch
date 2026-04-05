"""Tests for APO preset refine mode — refine imported presets against measurements."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from headmatch.apo_refine import refine_apo_preset, _refine_channel
from headmatch.peq import PEQBand, FitObjective, peq_chain_response_db
from headmatch.signals import SweepSpec, generate_log_sweep, geometric_log_grid
from headmatch.io_utils import write_wav


def _synthetic_sweep_spec() -> SweepSpec:
    return SweepSpec(
        sample_rate=48000,
        duration_s=1.25,
        pre_silence_s=0.05,
        post_silence_s=0.1,
        amplitude=0.35,
    )


def _peaking_sos(sample_rate: int, fc: float, q: float, gain_db: float) -> np.ndarray:
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / sample_rate
    alpha = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    b = np.array([1 + alpha * A, -2 * c, 1 - alpha * A])
    a = np.array([1 + alpha / A, -2 * c, 1 - alpha / A])
    return signal.tf2sos(b, a)


def _build_recording(tmp_path: Path) -> tuple[Path, SweepSpec]:
    spec = _synthetic_sweep_spec()
    stereo, _ = generate_log_sweep(spec)
    left_sos = np.vstack([
        _peaking_sos(spec.sample_rate, 85, 0.8, 5.0),
        _peaking_sos(spec.sample_rate, 2800, 1.4, 4.5),
    ])
    right_sos = np.vstack([
        _peaking_sos(spec.sample_rate, 95, 0.75, 4.0),
        _peaking_sos(spec.sample_rate, 3400, 1.6, 5.0),
    ])
    left = signal.sosfilt(left_sos, stereo[:, 0])
    right = signal.sosfilt(right_sos, stereo[:, 1]) * 0.96
    left = np.concatenate([np.zeros(90), left[:-90]])
    right = np.concatenate([np.zeros(120), right[:-120]])
    recording = np.column_stack([left, right])
    recording_path = tmp_path / "recording.wav"
    write_wav(recording_path, recording, spec.sample_rate)
    return recording_path, spec


def _write_apo_preset(path: Path, left_bands: list[PEQBand], right_bands: list[PEQBand]) -> Path:
    """Write a minimal APO parametric preset file."""
    lines = ["Preamp: 0 dB"]
    for label, bands in [("Channel: L", left_bands), ("Channel: R", right_bands)]:
        lines.append(label)
        for i, b in enumerate(bands, 1):
            kind_map = {"peaking": "PK", "lowshelf": "LS", "highshelf": "HS"}
            lines.append(f"Filter {i}: ON {kind_map[b.kind]} Fc {b.freq:.1f} Hz Gain {b.gain_db:.1f} dB Q {b.q:.2f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestRefineChannel:
    """Unit tests for single-channel refinement."""

    def test_refine_improves_or_preserves_error(self):
        """Refinement should not make the error worse."""
        freqs = geometric_log_grid()
        sr = 48000
        # Simulated measurement: flat
        measured = np.zeros_like(freqs)
        # Target: 3 dB boost at 1kHz
        target = np.zeros_like(freqs)
        target[(freqs > 800) & (freqs < 1200)] = 3.0

        # Slightly off starting bands
        bands = [PEQBand("peaking", 950.0, 2.5, 1.0), PEQBand("peaking", 3000.0, 1.0, 1.5)]

        eq_target = target - measured
        response_before = peq_chain_response_db(freqs, sr, bands)
        error_before = np.sqrt(np.mean((eq_target - response_before) ** 2))

        refined = _refine_channel(freqs, measured, target, bands, sr, 8.0, 4.5)
        response_after = peq_chain_response_db(freqs, sr, refined)
        error_after = np.sqrt(np.mean((eq_target - response_after) ** 2))

        # Refinement should improve or at worst preserve
        assert error_after <= error_before * 1.05, (
            f"Refinement made error worse: {error_before:.3f} → {error_after:.3f}"
        )

    def test_refine_empty_bands(self):
        """Empty band list should return empty."""
        freqs = geometric_log_grid()
        result = _refine_channel(freqs, np.zeros_like(freqs), np.zeros_like(freqs), [], 48000, 8.0, 4.5)
        assert result == []


class TestRefineApoPreset:
    """Integration test for full refine workflow."""

    def test_refine_produces_artifacts(self, tmp_path):
        """Full refine pipeline should produce all expected output files."""
        recording_path, spec = _build_recording(tmp_path)
        out_dir = tmp_path / "refined"

        # Create a starting preset (deliberately imperfect)
        preset_path = tmp_path / "preset.txt"
        _write_apo_preset(preset_path, 
            [PEQBand("peaking", 100.0, -3.0, 1.0), PEQBand("peaking", 2500.0, -2.0, 1.2)],
            [PEQBand("peaking", 100.0, -2.5, 0.9), PEQBand("peaking", 3000.0, -3.0, 1.4)],
        )

        report = refine_apo_preset(
            preset_path=preset_path,
            recording_wav=recording_path,
            sweep_spec=spec,
            out_dir=str(out_dir),
        )

        # Check report structure
        assert 'mode' in report
        assert report['mode'] == 'refine'
        assert 'original_error' in report
        assert 'predicted_left_rms_error_db' in report
        assert 'left_bands' in report
        assert 'right_bands' in report
        assert 'confidence' in report

        # Check artifacts exist
        assert (out_dir / 'equalizer_apo.txt').exists()
        assert (out_dir / 'camilladsp_full.yaml').exists()
        assert (out_dir / 'fit_report.json').exists()
        assert (out_dir / 'run_summary.json').exists()
        assert (out_dir / 'fit_overview.svg').exists()

    def test_refine_report_includes_before_after(self, tmp_path):
        """Report should show both original and refined error metrics."""
        recording_path, spec = _build_recording(tmp_path)
        out_dir = tmp_path / "refined2"
        preset_path = tmp_path / "preset2.txt"
        _write_apo_preset(preset_path,
            [PEQBand("peaking", 100.0, -3.0, 1.0)],
            [PEQBand("peaking", 100.0, -2.5, 0.9)],
        )

        report = refine_apo_preset(
            preset_path=preset_path,
            recording_wav=recording_path,
            sweep_spec=spec,
            out_dir=str(out_dir),
        )

        orig = report['original_error']
        assert 'left_rms' in orig
        assert 'right_rms' in orig
        # Both should be real numbers
        assert orig['left_rms'] >= 0
        assert report['predicted_left_rms_error_db'] >= 0
