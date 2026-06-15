"""End-to-end test of the offline workflow contract:

    prepare-offline  ->  analyze  ->  fit

`prepare-offline` writes a sweep WAV plus a `measurement_plan.json` describing
the exact sweep parameters used. The user records the played sweep on external
gear, and that recording must feed `analyze` (recovering the headphone
response) and `fit` (producing a correcting EQ) -- all driven by the parameters
learned from the metadata. This test proves that inter-command contract on
synthetic data with known ground truth (a real published HD 650 response
injected onto the prepared sweep), so no hardware/network is needed.
"""
from __future__ import annotations

import numpy as np

from headmatch import cli
from headmatch.io_utils import load_fr_csv, write_wav
from headmatch.signals import SweepSpec

from tests.test_integration_cli import (
    _patch_cli_config,
    _predicted_errors,
    _read_json,
    _synthetic_sweep_spec,
    flat_target_csv,
)
from tests.test_e2e_fitting import HD650_CSV, _inject_headset_channels


def _normalize_at_1k(freqs: np.ndarray, values: np.ndarray) -> np.ndarray:
    return values - values[int(np.argmin(np.abs(freqs - 1000.0)))]


def _sweep_args(spec: SweepSpec) -> list[str]:
    """CLI sweep flags reconstructed from a SweepSpec (as learned from metadata)."""
    return [
        "--sample-rate", str(spec.sample_rate),
        "--duration", str(spec.duration_s),
        "--f-start", str(spec.f_start),
        "--f-end", str(spec.f_end),
        "--pre-silence", str(spec.pre_silence_s),
        "--post-silence", str(spec.post_silence_s),
        "--amplitude", str(spec.amplitude),
    ]


def test_offline_workflow_prepare_analyze_fit_contract(monkeypatch, tmp_path):
    spec = _synthetic_sweep_spec()
    _patch_cli_config(monkeypatch, tmp_path)

    # ── 1. prepare-offline: write the sweep package, then inspect what it wrote.
    prep_dir = tmp_path / "session"
    cli.main(["prepare-offline", "--out-dir", str(prep_dir), "--notes", "e2e", *_sweep_args(spec)])

    metadata = _read_json(prep_dir / "measurement_plan.json")
    assert metadata["mode"] == "offline"
    # The metadata names the sweep WAV it produced, and that file exists.
    sweep_wav = prep_dir / "sweep.wav"
    assert sweep_wav.exists()
    assert metadata["files"]["sweep_wav"] == str(sweep_wav)

    # Contract: the recorded sweep parameters in the metadata match what we passed,
    # and the recommended capture format matches the sweep sample rate.
    recorded = metadata["sweep"]
    assert recorded["sample_rate"] == spec.sample_rate
    assert recorded["duration_s"] == spec.duration_s
    assert recorded["f_start"] == spec.f_start
    assert recorded["f_end"] == spec.f_end
    assert recorded["pre_silence_s"] == spec.pre_silence_s
    assert recorded["post_silence_s"] == spec.post_silence_s
    assert recorded["amplitude"] == spec.amplitude
    assert metadata["recommended_format"]["sample_rate"] == spec.sample_rate

    # Rebuild the SweepSpec purely from the metadata: downstream commands are
    # driven by what prepare-offline declared, not by our local `spec`.
    learned = SweepSpec(**recorded)
    assert learned == spec

    # ── 2. Synthesise "the user recording the played sweep": the prepared sweep
    #       colored by a real published HD 650 response, written at the metadata
    #       sample rate.
    recording, (inj_f, inj_g) = _inject_headset_channels(learned, HD650_CSV)
    recording_path = prep_dir / "recording.wav"
    write_wav(recording_path, recording, learned.sample_rate)

    # ── 3. analyze with the SAME params learned from the metadata.
    analyze_dir = tmp_path / "analysis"
    cli.main([
        "analyze",
        "--recording", str(recording_path),
        "--out-dir", str(analyze_dir),
        *_sweep_args(learned),
    ])

    assert (analyze_dir / "measurement_left.csv").exists()
    assert (analyze_dir / "measurement_right.csv").exists()

    # Contract: the analyzed response recovers the injected HD 650 shape
    # (1 kHz-normalised RMS deviation over ~120-7000 Hz below a few dB).
    freqs, left = load_fr_csv(analyze_dir / "measurement_left.csv")
    inj_on_grid = np.interp(np.log10(freqs), np.log10(inj_f), inj_g, left=inj_g[0], right=inj_g[-1])
    band = (freqs >= 120) & (freqs <= 7000)
    recovered = _normalize_at_1k(freqs, left)[band]
    injected = _normalize_at_1k(freqs, inj_on_grid)[band]
    recovered_rms = float(np.sqrt(np.mean((recovered - injected) ** 2)))
    assert recovered_rms < 4.0, f"analyze recovered {recovered_rms:.2f} dB RMS off the injected HD650 curve"

    # ── 4. fit the same recording (flat target), again driven by the metadata params.
    fit_dir = tmp_path / "fit"
    cli.main([
        "fit",
        "--recording", str(recording_path),
        "--out-dir", str(fit_dir),
        "--target-csv", str(flat_target_csv()),
        *_sweep_args(learned),
        "--max-filters", "5",
    ])

    # Contract: the fitted EQ reduces predicted error for both channels.
    errs = _predicted_errors(fit_dir, learned.sample_rate)
    assert errs["left_after"] < errs["left_before"], errs
    assert errs["right_after"] < errs["right_before"], errs

    # Contract: standard exports are written.
    assert (fit_dir / "equalizer_apo.txt").exists()
    assert (fit_dir / "equalizer_apo_graphiceq.txt").exists()
