"""End-to-end tests of the fitting workflows on synthetic data with known
ground truth (no real microphone / hardware required).

- Offline measurement fit: a real published headphone response (Sennheiser
  HD 650, docs/examples/clone-targets/hd650_published.csv) is convolved onto
  the analysis sweep to synthesise a recording, then the full offline pipeline
  must (a) recover that response and (b) produce an EQ that corrects it toward
  the target.
- Hearing-test fit: a typical middle-aged (presbycusis) sloping high-frequency
  loss must produce a high-frequency-weighted compensation EQ.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from headmatch.hearing_test import (
    NORMAL_HEARING_REFERENCE,
    MAX_COMPENSATION_DB,
    TEST_FREQUENCIES,
    FrequencyThreshold,
    HearingProfile,
)
import json

from headmatch.io_utils import load_fr_csv, write_wav
from headmatch.peq import PEQBand, peq_chain_response_db
from headmatch.pipeline import (
    iterative_measure_and_fit,
    process_single_measurement,
    run_hearing_fit,
)
from headmatch.signals import generate_log_sweep
from headmatch.targets import clone_target_from_source_target

from tests.test_integration_cli import _predicted_errors, _synthetic_sweep_spec

REPO = Path(__file__).resolve().parent.parent
CLONE_DIR = REPO / "docs" / "examples" / "clone-targets"
HD650_CSV = CLONE_DIR / "hd650_published.csv"
HD800S_CSV = CLONE_DIR / "hd800s_published.csv"


def _apply_fr(signal_mono: np.ndarray, freqs_hz: np.ndarray, gains_db: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply a magnitude frequency response (dB vs Hz) to a signal via FFT."""
    n = len(signal_mono)
    spectrum = np.fft.rfft(signal_mono)
    bin_freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    safe = np.clip(bin_freqs, 1e-6, None)
    g_db = np.interp(
        np.log10(safe), np.log10(freqs_hz), gains_db,
        left=gains_db[0], right=gains_db[-1],
    )
    return np.fft.irfft(spectrum * (10.0 ** (g_db / 20.0)), n=n)


def _inject_headset_channels(spec, csv_path: Path):
    """Synthesise a stereo recording = analysis sweep colored by a real
    published headphone response, with per-channel latency + noise."""
    stereo, _ = generate_log_sweep(spec)
    freqs, gains = load_fr_csv(csv_path)
    left = _apply_fr(stereo[:, 0], freqs, gains, spec.sample_rate)
    right = _apply_fr(stereo[:, 1], freqs, gains, spec.sample_rate)
    left = np.concatenate([np.zeros(90), left[:-90]]) + 0.00015 * np.random.default_rng(0).standard_normal(len(left))
    right = np.concatenate([np.zeros(120), right[:-120]]) + 0.00015 * np.random.default_rng(1).standard_normal(len(right))
    return np.column_stack([left, right]), (freqs, gains)


def _build_real_headset_recording(tmp_path: Path, csv_path: Path):
    spec = _synthetic_sweep_spec()
    recording, curve = _inject_headset_channels(spec, csv_path)
    recording_path = tmp_path / "recording.wav"
    write_wav(recording_path, recording, spec.sample_rate)
    return recording_path, spec, curve


def _normalize_at_1k(freqs: np.ndarray, values: np.ndarray) -> np.ndarray:
    return values - values[int(np.argmin(np.abs(freqs - 1000.0)))]


def test_offline_fit_e2e_recovers_real_headset_and_corrects_it(tmp_path):
    recording, spec, (inj_f, inj_g) = _build_real_headset_recording(tmp_path, HD650_CSV)
    out = tmp_path / "fit"

    report = process_single_measurement(recording, out, spec, target_path=None)  # flat target

    # All artifacts written.
    for name in ("equalizer_apo.txt", "equalizer_apo_graphiceq.txt", "measurement_left.csv", "fit_report.json"):
        assert (out / name).exists(), f"missing {name}"

    # (a) The analyzed response recovers the injected HD 650 curve (shape, 1 kHz-normalised).
    freqs, left = load_fr_csv(out / "measurement_left.csv")
    inj_on_grid = np.interp(np.log10(freqs), np.log10(inj_f), inj_g, left=inj_g[0], right=inj_g[-1])
    band = (freqs >= 120) & (freqs <= 7000)
    recovered = _normalize_at_1k(freqs, left)[band]
    injected = _normalize_at_1k(freqs, inj_on_grid)[band]
    rms = float(np.sqrt(np.mean((recovered - injected) ** 2)))
    assert rms < 4.0, f"recovered response deviates {rms:.2f} dB RMS from injected HD650 curve"

    # (b) The EQ corrects the real headphone toward the (flat) target.
    errs = _predicted_errors(out, spec.sample_rate)
    assert errs["left_after"] < errs["left_before"]
    assert errs["right_after"] < errs["right_before"]
    assert "left_bands" in report and report["left_bands"]


def test_clone_target_e2e_makes_hd650_sound_like_hd800s(tmp_path):
    # End-to-end clone workflow on real published curves: a clone target built
    # from HD 650 -> HD 800S, applied as a relative target while fitting a
    # synthesised HD 650 recording, should correct the HD 650 toward the HD 800S.
    clone_csv = tmp_path / "hd650_to_hd800s.csv"
    clone_target_from_source_target(HD650_CSV, HD800S_CSV, clone_csv)

    recording, spec, _ = _build_real_headset_recording(tmp_path, HD650_CSV)
    out = tmp_path / "clone_fit"
    process_single_measurement(recording, out, spec, target_path=clone_csv)

    freqs, left = load_fr_csv(out / "measurement_left.csv")
    report = json.loads((out / "fit_report.json").read_text())
    bands = [PEQBand(**b) for b in report["left_bands"]]
    corrected = left + peq_chain_response_db(freqs, spec.sample_rate, bands)

    f8, g8 = load_fr_csv(HD800S_CSV)
    hd800s = np.interp(np.log10(freqs), np.log10(f8), g8, left=g8[0], right=g8[-1])

    band = (freqs >= 120) & (freqs <= 7000)
    rms = float(np.sqrt(np.mean(
        (_normalize_at_1k(freqs, corrected)[band] - _normalize_at_1k(freqs, hd800s)[band]) ** 2
    )))
    assert rms < 4.0, f"cloned HD650 deviates {rms:.2f} dB RMS from HD800S target"


def _mock_capture_with(csv_path: Path):
    """Return a run_pipewire_measurement replacement that writes a synthetic
    recording (real headset response injected) instead of capturing hardware."""
    def _fake(spec, paths, _device):
        recording, _ = _inject_headset_channels(spec, csv_path)
        write_wav(paths.recording_wav, recording, spec.sample_rate)
        return paths.recording_wav
    return _fake


def test_iterative_measure_and_fit_e2e_average_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("headmatch.pipeline.run_pipewire_measurement", _mock_capture_with(HD650_CSV))
    spec = _synthetic_sweep_spec()

    summaries = iterative_measure_and_fit(
        tmp_path, spec, target_path=None, output_target=None, input_target=None,
        iterations=2, iteration_mode="average",
    )

    assert summaries
    for name in ("measurement_left.csv", "equalizer_apo.txt", "fit_report.json", "target_curve.csv"):
        assert (tmp_path / name).exists(), f"missing {name}"
    errs = _predicted_errors(tmp_path, spec.sample_rate)
    assert errs["left_after"] < errs["left_before"]
    assert errs["right_after"] < errs["right_before"]


def test_iterative_measure_and_fit_e2e_independent_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("headmatch.pipeline.run_pipewire_measurement", _mock_capture_with(HD650_CSV))
    spec = _synthetic_sweep_spec()

    summaries = iterative_measure_and_fit(
        tmp_path, spec, target_path=None, output_target=None, input_target=None,
        iterations=2, iteration_mode="independent",
    )

    # One summary + artifact folder per iteration.
    assert len(summaries) == 2
    for i in (1, 2):
        iter_dir = tmp_path / f"iter_{i:02d}"
        assert (iter_dir / "equalizer_apo.txt").exists()
        assert (iter_dir / "fit_report.json").exists()


# A representative middle-aged (presbycusis) audiogram: gentle low-frequency
# loss sloping to a moderate high-frequency loss (dB above the normal reference).
_PRESBYCUSIS_LOSS_DB = {500: 5, 1000: 8, 2000: 13, 3000: 22, 4000: 32, 6000: 40, 8000: 48}


def _presbycusis_profile() -> HearingProfile:
    side = {
        f: FrequencyThreshold(
            freq_hz=f,
            level_dbfs=NORMAL_HEARING_REFERENCE[f] + _PRESBYCUSIS_LOSS_DB[f],
            ascending_runs=3,
            determined=True,
        )
        for f in TEST_FREQUENCIES
    }
    return HearingProfile(left=dict(side), right=dict(side), tested_at="2026-01-01T00:00:00+00:00", asymmetric_freqs=[])


def test_hearing_fit_e2e_presbycusis_boosts_high_frequencies(tmp_path):
    profile = _presbycusis_profile()
    report = run_hearing_fit(profile, tmp_path, sample_rate=48000)

    assert report["mode"] == "hearing_only"
    for name in ("equalizer_apo.txt", "equalizer_apo_graphiceq.txt", "hearing_fit_report.json", "README.txt"):
        assert (tmp_path / name).exists(), f"missing {name}"

    bands = report["left_bands"]
    assert bands, "expected compensation bands for presbycusis"
    by_freq = {round(b["freq"]): b["gain_db"] for b in bands}
    # High-frequency boost must exceed low-frequency boost (sloping loss).
    assert max(by_freq) >= 6000
    assert by_freq[max(by_freq)] > by_freq[min(by_freq)]
    # Gains respect the compensation cap.
    assert all(b["gain_db"] <= MAX_COMPENSATION_DB + 1e-6 for b in bands)

    # Compact GraphicEQ (measured points + anchors), not a dense grid.
    gq = [ln for ln in (tmp_path / "equalizer_apo_graphiceq.txt").read_text().splitlines() if ln.startswith("GraphicEQ:")]
    assert gq and len(gq[0].split(":", 1)[1].split(";")) <= 12
