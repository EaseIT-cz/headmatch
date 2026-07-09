"""End-to-end tests for run_room_fit covering PR#35 review fixes.

- Non-48 kHz / non-default sweeps must flow through from the caller's SweepSpec
  (previously run_room_fit hardcoded 48 kHz / 8 s and crashed on other rates).
- Bass-only room target CSVs (≤ cutoff) must load without a 1 kHz anchor.
- Target semantics ('relative' vs 'absolute') must be honored.
"""
from __future__ import annotations

import numpy as np

from headmatch.io_utils import write_wav
from headmatch.room import run_room_fit
from headmatch.signals import SweepSpec, generate_log_sweep


def _make_room_recording(tmp_path, spec: SweepSpec, name: str = "room.wav"):
    _, mono = generate_log_sweep(spec)
    pre = np.zeros(int(spec.pre_silence_s * spec.sample_rate))
    post = np.zeros(int(spec.post_silence_s * spec.sample_rate))
    cap = np.concatenate([pre, mono, post]).reshape(-1, 1)
    path = tmp_path / name
    write_wav(path, cap, spec.sample_rate)
    return path


def test_run_room_fit_honors_non_48k_sweep_spec(tmp_path):
    # 44.1 kHz is a common field-recorder default; this crashed before the fix.
    spec = SweepSpec(sample_rate=44100, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    recording = _make_room_recording(tmp_path, spec)
    out_dir = tmp_path / "out"

    result = run_room_fit(
        recording=recording,
        recording_two=None,
        mic_cal=None,
        cutoff_hz=300.0,
        max_boost_db=2.0,
        target_csv=None,
        out_dir=out_dir,
        sweep_spec=spec,
    )

    assert result.run_summary["sample_rate"] == 44100
    assert (out_dir / "equalizer_apo.txt").exists()
    # Every band stays within the boost ceiling and the modal band.
    assert all(b.gain_db <= 2.0 + 1e-6 for b in result.eq_bands)
    assert all(b.freq <= 300.0 + 1e-6 for b in result.eq_bands)


def test_run_room_fit_accepts_bass_only_target_csv(tmp_path):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    recording = _make_room_recording(tmp_path, spec)

    # A target that spans only the modal band (20-300 Hz) — never reaches 1 kHz.
    target_csv = tmp_path / "bass_only_target.csv"
    target_csv.write_text(
        "# headmatch_target_semantics=absolute\n"
        "frequency_hz,target_db\n"
        "20,-2.0\n50,-1.0\n100,0.0\n200,0.0\n300,0.0\n"
    )
    out_dir = tmp_path / "out"

    # Must not raise (previously crashed in normalize_at_1khz).
    result = run_room_fit(
        recording=recording,
        recording_two=None,
        mic_cal=None,
        cutoff_hz=300.0,
        max_boost_db=2.0,
        target_csv=target_csv,
        out_dir=out_dir,
        sweep_spec=spec,
    )
    assert (out_dir / "target_curve.csv").exists()
    assert result.target.freqs_hz.shape == result.result.freqs_hz.shape


def test_run_room_fit_honors_relative_target_semantics(tmp_path):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    recording = _make_room_recording(tmp_path, spec)

    values = "20,3.0\n50,3.0\n100,3.0\n200,3.0\n300,3.0\n1000,3.0\n"
    absolute_csv = tmp_path / "abs_target.csv"
    absolute_csv.write_text("# headmatch_target_semantics=absolute\nfrequency_hz,target_db\n" + values)
    relative_csv = tmp_path / "rel_target.csv"
    relative_csv.write_text("# headmatch_target_semantics=relative\nfrequency_hz,target_db\n" + values)

    def _fit(csv, out_name):
        return run_room_fit(
            recording=recording, recording_two=None, mic_cal=None,
            cutoff_hz=300.0, max_boost_db=12.0, target_csv=csv,
            out_dir=tmp_path / out_name, sweep_spec=spec,
        )

    abs_res = _fit(absolute_csv, "abs_out")
    rel_res = _fit(relative_csv, "rel_out")

    # Absolute: eq_target = target - measured. Relative: eq_target = target.
    # With a non-trivial measured response these must yield different EQ, proving
    # semantics is honored rather than silently treated as absolute.
    abs_gains = sorted(round(b.gain_db, 3) for b in abs_res.eq_bands)
    rel_gains = sorted(round(b.gain_db, 3) for b in rel_res.eq_bands)
    assert abs_gains != rel_gains
