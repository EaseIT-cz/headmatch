# TASK-117 — Room measurement & modal correction

Design reference: `docs/designs/room-measurement.md`.

This plan is written to be implemented task-by-task by any developer. Each task is
test-driven: write the failing test, confirm it fails, implement, confirm it passes,
then commit. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `room-measure` / `room-fit` workflow that measures a speaker-in-room response with a calibrated USB mic and produces a bass-only (≤ cutoff) corrective EQ, reusing the existing sweep → align → Wiener-FR → PEQ → export spine.

**Architecture:** Two new modules — `mic_cal.py` (parse + apply a measurement-mic calibration file) and `room.py` (room orchestration) — plus small, backward-compatible extensions to `analysis.py` (mono-aware analysis), `peq.py` (band-limit + high-Q fitting), `plots.py` (cutoff marker), `contracts.py`, `measure.py`, and `cli.py`. The mono room FR is represented as a `MeasurementResult` with `left_db == right_db` so the confidence scorer and exporters are reused unchanged.

**Tech Stack:** Python 3.10–3.13, numpy, scipy, soundfile, argparse, pytest. No new third-party dependencies.

## Global Constraints

- **No new runtime dependencies** — numpy/scipy/soundfile only (matches existing modules).
- **Every module starts with** `from __future__ import annotations`.
- **All new public functions are pure where possible** — no GUI/audio coupling in `mic_cal.py` and the fit core of `room.py`; audio I/O only in the online `room-measure` path.
- **Backward compatibility is mandatory** — new parameters on `fit_peq` and `render_fit_graphs` MUST default to current behaviour. Existing tests must stay green.
- **Correction band is bass-only:** no fitted filter may have a centre frequency above `cutoff_hz`. Default cutoff `ROOM_CUTOFF_DEFAULT_HZ = 300.0`.
- **Boosts are hard-capped:** no fitted band gain may exceed `ROOM_MAX_BOOST_DB = 2.0`; cuts may go to `-12.0 dB`.
- **Mic calibration is relative-FR-only:** absolute SPL / `Sens Factor` lines are parsed past and discarded.
- **Mono EQ output:** `left_bands == right_bands`; the same correction is applied to both channels.
- **Test command:** `python -m pytest -q` from repo root. New tests live in `tests/`.
- **Commit style:** small commits per step; no `Co-Authored-By` trailer (project rule).
- **Execution order:** implement tasks **1 → 2 → 3 → 5 → 4 → 6 → 7**. Tasks are numbered by subsystem, but Task 4 (`room.py`) calls `render_fit_graphs(..., cutoff_hz=)`, which Task 5 adds — so Task 5 must land before Task 4.

---

### Task 1: Microphone calibration module (`mic_cal.py`)

**Files:**
- Create: `headmatch/mic_cal.py`
- Test: `tests/test_mic_cal.py`

**Interfaces:**
- Consumes: `numpy`, `scipy.interpolate.PchipInterpolator`, `pathlib.Path`.
- Produces:
  - `MicCalibration` dataclass: `freqs_hz: np.ndarray`, `gains_db: np.ndarray`, `source: str`.
  - `load_mic_calibration(path: str | Path) -> MicCalibration`
  - `calibration_offset(cal: MicCalibration, freq_grid: np.ndarray) -> np.ndarray` — dB offset per grid point, held-flat (clamped to endpoint values) outside the cal file's range.
  - Constants: `MIC_CAL_MIN_HZ = 20.0`, `MIC_CAL_MAX_HZ = 500.0`, `MIC_CAL_PLAUSIBLE_ABS_DB = 30.0`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mic_cal.py
from __future__ import annotations

import numpy as np
import pytest

from headmatch.mic_cal import (
    MIC_CAL_PLAUSIBLE_ABS_DB,
    MicCalibration,
    calibration_offset,
    load_mic_calibration,
)


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_umik_style_with_sens_factor_and_comments(tmp_path):
    csv = _write(tmp_path / "umik.txt", (
        '"Sens Factor =-1.3dB, SERNO: 7012345"\n'
        "* a comment line\n"
        "20.000\t-2.50\n"
        "100.000, 0.40\n"
        "1000.000 0.00\n"
        "500.000\t0.10\n"
    ))
    cal = load_mic_calibration(csv)
    # rows sorted ascending by frequency, sens-factor/comment lines skipped
    assert list(cal.freqs_hz) == [20.0, 100.0, 500.0, 1000.0]
    assert cal.gains_db[0] == pytest.approx(-2.5)
    assert cal.gains_db[-1] == pytest.approx(0.0)


def test_tolerates_column_header_line(tmp_path):
    csv = _write(tmp_path / "h.csv", (
        "Frequency(Hz),Magnitude(dB)\n"
        "20,-1.0\n2000,0.5\n"
    ))
    cal = load_mic_calibration(csv)
    assert list(cal.freqs_hz) == [20.0, 2000.0]


def test_rejects_implausible_scale(tmp_path):
    # ±50 dB values are a measurement/target CSV handed in by mistake, not a cal file.
    csv = _write(tmp_path / "wrong.csv", "20,-48.0\n1000,0.0\n2000,52.0\n")
    with pytest.raises(ValueError, match="calibration"):
        load_mic_calibration(csv)


def test_warns_when_coverage_insufficient(tmp_path, recwarn):
    csv = _write(tmp_path / "narrow.csv", "200,-0.2\n400,0.1\n")  # only 200-400 Hz
    cal = load_mic_calibration(csv)
    assert any("20" in str(w.message) for w in recwarn.list)
    assert list(cal.freqs_hz) == [200.0, 400.0]


def test_offset_interpolates_and_holds_flat_outside_range(tmp_path):
    csv = _write(tmp_path / "c.csv", "50,-2.0\n100,0.0\n200,2.0\n")
    cal = load_mic_calibration(csv)
    grid = np.array([10.0, 50.0, 100.0, 200.0, 5000.0])
    off = calibration_offset(cal, grid)
    assert off[1] == pytest.approx(-2.0)   # at 50 Hz
    assert off[2] == pytest.approx(0.0)    # at 100 Hz
    assert off[0] == pytest.approx(-2.0)   # below range -> held at first value
    assert off[4] == pytest.approx(2.0)    # above range -> held at last value
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mic_cal.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'headmatch.mic_cal'`.

- [ ] **Step 3: Write the implementation**

```python
# headmatch/mic_cal.py
"""Measurement-microphone calibration: parse a UMIK-1-style calibration file
and apply it as a relative frequency-response correction.

Relative-FR only: any absolute-SPL sensitivity line (e.g. ``Sens Factor =-1.3dB``)
is parsed past and discarded — room modal EQ does not use absolute SPL.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

MIC_CAL_MIN_HZ = 20.0
MIC_CAL_MAX_HZ = 500.0
# A real microphone calibration curve spans a few dB. Values far larger than
# this mean the file is almost certainly a measurement/target CSV by mistake.
MIC_CAL_PLAUSIBLE_ABS_DB = 30.0

_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class MicCalibration:
    freqs_hz: np.ndarray
    gains_db: np.ndarray
    source: str


def _parse_rows(path: Path) -> list[tuple[float, float]]:
    rows: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in "#*\"'":  # comment / quoted Sens Factor line
            continue
        # Split on comma, tab, or whitespace; keep only the numeric tokens.
        tokens = _NUMBER.findall(stripped)
        if len(tokens) < 2:
            continue  # header like "Frequency(Hz),Magnitude(dB)" has no leading number pair
        try:
            freq = float(tokens[0])
            gain = float(tokens[1])
        except ValueError:
            continue
        if freq <= 0:
            continue
        rows.append((freq, gain))
    return rows


def load_mic_calibration(path: str | Path) -> MicCalibration:
    path = Path(path)
    rows = _parse_rows(path)
    if len(rows) < 2:
        raise ValueError(f"No usable calibration rows found in {path}")
    rows.sort(key=lambda r: r[0])
    freqs = np.array([r[0] for r in rows], dtype=np.float64)
    gains = np.array([r[1] for r in rows], dtype=np.float64)
    if np.max(np.abs(gains)) > MIC_CAL_PLAUSIBLE_ABS_DB:
        raise ValueError(
            f"{path} does not look like a microphone calibration file: values exceed "
            f"±{MIC_CAL_PLAUSIBLE_ABS_DB:g} dB. A real cal curve spans a few dB."
        )
    if freqs[0] > MIC_CAL_MIN_HZ or freqs[-1] < MIC_CAL_MAX_HZ:
        warnings.warn(
            f"Mic calibration {path} spans {freqs[0]:.0f}-{freqs[-1]:.0f} Hz; "
            f"recommended coverage is at least {MIC_CAL_MIN_HZ:.0f}-{MIC_CAL_MAX_HZ:.0f} Hz.",
            stacklevel=2,
        )
    return MicCalibration(freqs_hz=freqs, gains_db=gains, source=str(path))


def calibration_offset(cal: MicCalibration, freq_grid: np.ndarray) -> np.ndarray:
    """dB offset to ADD to a measured response to remove the mic's own colouration.

    PCHIP interpolation on the cal points; held flat (endpoint value) outside the
    cal file's frequency range rather than extrapolated.
    """
    grid = np.asarray(freq_grid, dtype=np.float64)
    interp = PchipInterpolator(cal.freqs_hz, cal.gains_db, extrapolate=False)
    out = interp(grid)
    out = np.where(grid < cal.freqs_hz[0], cal.gains_db[0], out)
    out = np.where(grid > cal.freqs_hz[-1], cal.gains_db[-1], out)
    return out.astype(np.float64)
```

Note on convention: HeadMatch applies the cal as an additive correction to the measured dB curve. UMIK files express the mic's deviation; the sign convention here matches the existing `save_fr_csv`/curve handling (offset added to measured magnitude). The `test_offset_interpolates_*` test pins the exact behaviour.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mic_cal.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add headmatch/mic_cal.py tests/test_mic_cal.py
git commit -m "feat(room): add microphone calibration parsing and application"
```

---

### Task 2: Mono-aware room analysis (`analyze_room_measurement`)

**Files:**
- Modify: `headmatch/analysis.py` (add a new public function; reuse the existing private `_align_recording_to_reference` and `_fr_from_signals`)
- Test: `tests/test_room_analysis.py`

**Interfaces:**
- Consumes: `read_wav`, `_align_recording_to_reference`, `_fr_from_signals`, `geometric_log_grid`, `fractional_octave_smoothing`, `generate_log_sweep`, `MeasurementResult` (all already in `analysis.py` / `signals.py`).
- Produces:
  - `analyze_room_measurement(recording_wav: str | Path, sweep_spec: SweepSpec, mic_channel: int = 0, out_dir: str | Path | None = None) -> MeasurementResult` — returns a `MeasurementResult` whose `left_db == right_db` (and `left_raw_db == right_raw_db`) hold the single corrected mono response. `diagnostics['channel_mismatch_rms_db'] == 0.0`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_room_analysis.py
from __future__ import annotations

import numpy as np

from headmatch.analysis import analyze_room_measurement
from headmatch.io_utils import write_wav
from headmatch.signals import SweepSpec, generate_log_sweep


def _make_room_recording(tmp_path, latency_samples=0, channels=1):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    stereo, mono = generate_log_sweep(spec)
    # Build a mono "mic" capture: silence + sweep + silence, optionally delayed.
    pre = np.zeros(int(spec.pre_silence_s * spec.sample_rate) + latency_samples)
    post = np.zeros(int(spec.post_silence_s * spec.sample_rate))
    cap = np.concatenate([pre, mono, post])
    if channels == 1:
        data = cap.reshape(-1, 1)
    else:
        data = np.column_stack([cap, cap])
    path = tmp_path / "room.wav"
    write_wav(path, data, spec.sample_rate)
    return path, spec


def test_accepts_mono_capture_and_returns_symmetric_result(tmp_path):
    path, spec = _make_room_recording(tmp_path, channels=1)
    result = analyze_room_measurement(path, spec)
    assert result.left_db.shape == result.freqs_hz.shape
    np.testing.assert_array_equal(result.left_db, result.right_db)
    np.testing.assert_array_equal(result.left_raw_db, result.right_raw_db)
    assert result.diagnostics["channel_mismatch_rms_db"] == 0.0
    # 1 kHz normalisation anchor: response at 1 kHz is ~0 dB
    one_k = float(np.interp(1000.0, result.freqs_hz, result.left_db))
    assert abs(one_k) < 0.5


def test_alignment_tolerates_large_round_trip_latency(tmp_path):
    # Simulated USB-mic latency of ~50 ms must not break alignment / clip the sweep.
    path_a, spec = _make_room_recording(tmp_path, latency_samples=0, channels=1)
    result_a = analyze_room_measurement(path_a, spec)
    path_b, _ = _make_room_recording(tmp_path, latency_samples=2400, channels=1)  # 50 ms @ 48k
    result_b = analyze_room_measurement(path_b, spec)
    # Same underlying sweep -> recovered FR should match within a small tolerance.
    rms_diff = float(np.sqrt(np.mean((result_a.left_db - result_b.left_db) ** 2)))
    assert rms_diff < 1.0


def test_accepts_stereo_capture_using_selected_channel(tmp_path):
    path, spec = _make_room_recording(tmp_path, channels=2)
    result = analyze_room_measurement(path, spec, mic_channel=0)
    assert result.left_db.shape == result.freqs_hz.shape
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_room_analysis.py -q`
Expected: FAIL with `ImportError: cannot import name 'analyze_room_measurement'`.

- [ ] **Step 3: Write the implementation**

Append to `headmatch/analysis.py` (after `analyze_measurement`):

```python
def analyze_room_measurement(
    recording_wav: str | Path,
    sweep_spec: SweepSpec,
    mic_channel: int = 0,
    out_dir: str | Path | None = None,
) -> MeasurementResult:
    """Analyse a single-microphone room sweep recording.

    Unlike ``analyze_measurement`` (which requires a two-ear stereo capture),
    this accepts a mono capture (or one channel of a multichannel file) and
    returns a ``MeasurementResult`` with ``left_db == right_db`` so the rest of
    the pipeline (confidence scoring, exporters) can be reused unchanged.
    """
    recording, sr = read_wav(recording_wav)  # always 2D: (n, channels)
    if sr != sweep_spec.sample_rate:
        raise ValueError(f'Sample rate mismatch: recording {sr}, expected {sweep_spec.sample_rate}')
    if recording.ndim != 2 or len(recording) == 0:
        raise ValueError(f'{recording_wav} must be a non-empty 2D audio array')
    channel = min(max(int(mic_channel), 0), recording.shape[1] - 1)
    mic = recording[:, channel]

    min_len = int(round((sweep_spec.pre_silence_s + sweep_spec.duration_s * 0.5) * sweep_spec.sample_rate))
    if len(mic) < min_len:
        raise ValueError(f'Recording too short: {len(mic)} samples; expected at least {min_len}')

    from .signals import generate_log_sweep
    _, reference = generate_log_sweep(sweep_spec)
    padded_len = int(round((sweep_spec.pre_silence_s + sweep_spec.duration_s + sweep_spec.post_silence_s) * sweep_spec.sample_rate))
    padded = np.zeros(padded_len)
    start = int(round(sweep_spec.pre_silence_s * sweep_spec.sample_rate))
    padded[start:start + len(reference)] = reference

    aligned, alignment_diagnostics = _align_recording_to_reference(mic.reshape(-1, 1), padded)
    mono = aligned[:, 0]

    freqs, raw = _fr_from_signals(padded, mono, sr)
    grid = geometric_log_grid(20, min(20000, sr / 2 - 1), 48)
    interp = np.interp(grid, freqs, raw)
    norm = interp - np.interp(1000.0, grid, interp)
    smoothed = fractional_octave_smoothing(grid, norm, fraction=12)

    mask = _band_mask(grid)
    diagnostics = {
        **alignment_diagnostics,
        'left_roughness_db': _roughness_db(norm, smoothed, mask),
        'right_roughness_db': _roughness_db(norm, smoothed, mask),
        'channel_mismatch_rms_db': 0.0,  # single microphone — no channel mismatch
        'capture_rms_dbfs': float(20 * np.log10(max(np.sqrt(np.mean(aligned ** 2)), 1e-12))),
    }
    result = MeasurementResult(
        freqs_hz=grid,
        left_db=smoothed,
        right_db=smoothed.copy(),
        left_raw_db=norm,
        right_raw_db=norm.copy(),
        diagnostics=diagnostics,
    )
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_fr_csv(out_dir / 'room_fr.csv', result.freqs_hz, result.left_db)
        save_fr_csv(out_dir / 'room_fr_raw.csv', result.freqs_hz, result.left_raw_db)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_room_analysis.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `python -m pytest -q`
Expected: PASS (existing tests still green; new analysis function is additive).

- [ ] **Step 6: Commit**

```bash
git add headmatch/analysis.py tests/test_room_analysis.py
git commit -m "feat(room): add mono-aware room measurement analysis"
```

---

### Task 3: Band-limit + high-Q fitting support in `peq.py`

**Files:**
- Modify: `headmatch/peq.py` — `_max_q_for_frequency`, `_peaking_candidate`, `_select_peaking_candidate`, `_refine_bands_jointly`, `fit_peq`
- Test: `tests/test_peq_room_constraints.py`

**Interfaces:**
- Consumes: existing `peq.py` internals.
- Produces (new keyword-only params on the public `fit_peq`, all backward-compatible):
  - `fit_peq(..., *, budget=None, max_freq_hz: float | None = None, low_freq_q_cap: float | None = None, max_boost_db: float | None = None)`
  - When `max_freq_hz` is set, **no returned band has `freq > max_freq_hz`** (enforced in candidate selection AND joint refinement).
  - When `low_freq_q_cap` is set, it replaces the default 2.0 Q ceiling below 120 Hz, allowing narrow modal cuts.
  - When `max_boost_db` is set, **no returned band has `gain_db > max_boost_db`**, enforced as an *asymmetric* clamp in greedy placement AND in joint Nelder-Mead refinement (cuts still go to `-max_gain_db`). This makes the room boost ceiling structural — the optimizer never explores gains it will later have to clamp away. Default `None` ⇒ symmetric `±max_gain_db` (current behaviour).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_peq_room_constraints.py
from __future__ import annotations

import numpy as np

from headmatch.peq import fit_peq
from headmatch.signals import geometric_log_grid


def _target_with_peak(center_hz, gain_db, q_octaves=0.15):
    freqs = geometric_log_grid(20, 20000, 48)
    # A narrow +gain bump centred at center_hz (so eq_target wants a cut there).
    bump = gain_db * np.exp(-0.5 * (np.log2(freqs / center_hz) / q_octaves) ** 2)
    eq_target = -bump  # to correct a +gain room mode, EQ must cut
    return freqs, eq_target


def test_no_band_above_max_freq():
    freqs, eq_target = _target_with_peak(2000.0, 6.0)  # feature well above cutoff
    bands = fit_peq(freqs, eq_target, 48000, max_filters=8,
                    max_gain_db=12.0, max_q=12.0, max_freq_hz=300.0)
    assert all(b.freq <= 300.0 + 1e-6 for b in bands)


def test_allows_narrow_low_frequency_cut():
    # A sharp +6 dB mode at 60 Hz: with the default Q cap (2.0) it would be
    # smoothed away; with low_freq_q_cap it should be matched with high Q.
    freqs, eq_target = _target_with_peak(60.0, 6.0, q_octaves=0.12)
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6,
                    max_gain_db=12.0, max_q=12.0, max_freq_hz=300.0,
                    low_freq_q_cap=12.0)
    low_bands = [b for b in bands if b.freq < 120.0 and b.gain_db < 0]
    assert low_bands, "expected a corrective cut below 120 Hz"
    assert max(b.q for b in low_bands) > 2.0


def test_defaults_unchanged_when_new_args_absent():
    # Regression guard: the default low-frequency Q cap is still 2.0.
    freqs, eq_target = _target_with_peak(60.0, 6.0, q_octaves=0.12)
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6)
    low_bands = [b for b in bands if b.freq < 120.0]
    assert all(b.q <= 2.0 + 1e-6 for b in low_bands)


def test_asymmetric_boost_cap_survives_joint_refinement():
    # Several deep nulls would each "want" a large boost; max_boost_db must bound
    # every returned band's gain even after joint Nelder-Mead refinement runs.
    freqs = geometric_log_grid(20, 20000, 48)
    eq_target = (8.0 * np.exp(-0.5 * (np.log2(freqs / 60.0) / 0.12) ** 2)
                 + 8.0 * np.exp(-0.5 * (np.log2(freqs / 90.0) / 0.12) ** 2))  # wants +8 dB boosts
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6,
                    max_gain_db=12.0, max_q=8.0, max_freq_hz=300.0,
                    low_freq_q_cap=8.0, max_boost_db=2.0)
    assert bands, "expected bands"
    assert all(b.gain_db <= 2.0 + 1e-6 for b in bands)
    # Cuts are still allowed to go well below the boost ceiling.
    assert any(b.gain_db < -2.0 for b in fit_peq(
        freqs, -eq_target, 48000, max_filters=6, max_gain_db=12.0,
        max_q=8.0, max_freq_hz=300.0, low_freq_q_cap=8.0, max_boost_db=2.0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_peq_room_constraints.py -q`
Expected: FAIL — `fit_peq() got an unexpected keyword argument 'max_freq_hz'`.

- [ ] **Step 3: Modify `_max_q_for_frequency`**

Replace (peq.py:327-332):

```python
def _max_q_for_frequency(freq_hz: float, requested_max_q: float, low_freq_q_cap: float = 2.0) -> float:
    if freq_hz < 120:
        return min(requested_max_q, low_freq_q_cap)
    if freq_hz > 6000:
        return min(requested_max_q, 3.0)
    return requested_max_q
```

- [ ] **Step 4: Thread the caps through candidate selection**

In `_peaking_candidate` (peq.py:346-376), change the signature, the frequency clamp, the Q cap, and the gain clamp (which becomes asymmetric):

```python
def _peaking_candidate(
    objective: FitObjective,
    residual: np.ndarray,
    idx: int,
    *,
    max_gain_db: float,
    max_q: float,
    raw_residual: np.ndarray | None = None,
    max_freq_hz: float | None = None,
    low_freq_q_cap: float = 2.0,
    max_boost_db: float | None = None,
) -> PEQBand:
    peak_db = float(residual[idx])
    # Defence-in-depth only: _select_peaking_candidate already SKIPS any idx whose
    # frequency exceeds max_freq_hz, so this clip never relocates a real candidate
    # when max_freq_hz is set. It just bounds fc against Nyquist in the default path.
    upper = (objective.sample_rate / 2 - 500.0) if max_freq_hz is None else min(max_freq_hz, objective.sample_rate / 2 - 500.0)
    fc = float(np.clip(objective.freqs_hz[idx], 35.0, upper))
    # ... unchanged bandwidth search (sets `q`) ...
    q_limit = _max_q_for_frequency(fc, max_q, low_freq_q_cap)
    q = float(np.clip(1.0 / bw_oct, 0.45, q_limit))
    boost_limit = max_gain_db if max_boost_db is None else max_boost_db
    gain = float(np.clip(peak_db, -max_gain_db, boost_limit))
    if q >= 2.8:
        gain *= 0.85
    return PEQBand("peaking", fc, gain, q)
```

(Keep the existing bandwidth-search body that computes `bw_oct`/`q` exactly as-is; only the `q_limit`, `gain` clamp, and final lines shown above change.)

In `_select_peaking_candidate` (peq.py:379-402), add the two params and forward them:

```python
def _select_peaking_candidate(
    objective: FitObjective,
    residual: np.ndarray,
    bands: List[PEQBand],
    *,
    max_gain_db: float,
    max_q: float,
    min_peak_db: float,
    min_gain_db: float,
    allow_nearby_same_sign: bool,
    max_freq_hz: float | None = None,
    low_freq_q_cap: float = 2.0,
    max_boost_db: float | None = None,
) -> PEQBand | None:
    raw_residual = objective.raw_residual_db(bands)
    weighted = residual * objective.weights
    for idx in np.argsort(np.abs(weighted))[::-1]:
        peak_db = float(weighted[idx] / objective.weights[idx])
        if abs(peak_db) < min_peak_db:
            break
        if max_freq_hz is not None and objective.freqs_hz[idx] > max_freq_hz:
            continue
        candidate = _peaking_candidate(
            objective, residual, int(idx),
            max_gain_db=max_gain_db, max_q=max_q, raw_residual=raw_residual,
            max_freq_hz=max_freq_hz, low_freq_q_cap=low_freq_q_cap,
            max_boost_db=max_boost_db,
        )
        if abs(candidate.gain_db) < min_gain_db:
            continue
        if not allow_nearby_same_sign and _nearby_same_sign_band_exists(bands, candidate):
            continue
        return candidate
    return None
```

- [ ] **Step 5: Bound joint refinement**

In `_refine_bands_jointly` (peq.py:405-445), add `max_freq_hz` + `max_boost_db` and clamp the frequency and gain upper bounds. This is the site the review flagged — the optimizer itself must respect the asymmetric boost ceiling, otherwise it can drive a band's gain back above the ceiling after greedy placement:

```python
def _refine_bands_jointly(
    objective: FitObjective,
    bands: List[PEQBand],
    *,
    max_gain_db: float,
    max_q: float,
    max_freq_hz: float | None = None,
    max_boost_db: float | None = None,
) -> List[PEQBand]:
    from scipy.optimize import minimize
    peaking_indices = [i for i, b in enumerate(bands) if b.kind == 'peaking']
    if len(peaking_indices) < 2:
        return bands
    freq_upper = (objective.sample_rate / 2 - 200) if max_freq_hz is None else min(max_freq_hz, objective.sample_rate / 2 - 200)
    gain_upper = max_gain_db if max_boost_db is None else max_boost_db

    def _bands_from_params(params: np.ndarray) -> List[PEQBand]:
        result = list(bands)
        for pi, i in enumerate(peaking_indices):
            freq = float(np.clip(params[pi * 3], 25.0, freq_upper))
            gain = float(np.clip(params[pi * 3 + 1], -max_gain_db, gain_upper))
            q = float(np.clip(params[pi * 3 + 2], 0.3, max_q))
            result[i] = PEQBand('peaking', freq, gain, q)
        return result
    # ... rest of the function body unchanged ...
```

- [ ] **Step 6: Add params to `fit_peq` and forward them**

In `fit_peq` (peq.py:448-535), extend the signature and pass through the three internal calls:

```python
def fit_peq(
    freqs_hz: np.ndarray,
    target_eq_db: np.ndarray,
    sample_rate: int,
    max_filters: int = 8,
    max_gain_db: float = 8.0,
    max_q: float = 4.5,
    *,
    budget: FilterBudget | None = None,
    max_freq_hz: float | None = None,
    low_freq_q_cap: float | None = None,
    max_boost_db: float | None = None,
) -> List[PEQBand]:
    budget = (budget or FilterBudget(max_filters=max_filters)).normalized()
    if budget.family == "graphic_eq":
        return fit_fixed_band_graphic_eq(freqs_hz, target_eq_db, sample_rate, budget=budget, max_gain_db=max_gain_db)
    if budget.family != "peq":
        raise ValueError(f"Unsupported filter family: {budget.family}")
    low_cap = 2.0 if low_freq_q_cap is None else low_freq_q_cap
    objective = FitObjective.from_target(freqs_hz, target_eq_db, sample_rate)
    bands: List[PEQBand] = []
    # ... shelf-candidate block unchanged ...
    while len(bands) < budget.max_filters:
        residual = objective.residual_db(bands)
        candidate = _select_peaking_candidate(
            objective, residual, bands,
            max_gain_db=max_gain_db, max_q=max_q,
            min_peak_db=0.75, min_gain_db=0.6, allow_nearby_same_sign=False,
            max_freq_hz=max_freq_hz, low_freq_q_cap=low_cap, max_boost_db=max_boost_db,
        )
        if candidate is not None:
            bands.append(candidate)
            continue
        if budget.fill_policy != "exact_n":
            break
        candidate = _select_peaking_candidate(
            objective, residual, bands,
            max_gain_db=max_gain_db, max_q=max_q,
            min_peak_db=0.0, min_gain_db=0.0, allow_nearby_same_sign=False,
            max_freq_hz=max_freq_hz, low_freq_q_cap=low_cap, max_boost_db=max_boost_db,
        )
        if candidate is None:
            candidate = _select_peaking_candidate(
                objective, residual, bands,
                max_gain_db=max_gain_db, max_q=max_q,
                min_peak_db=0.0, min_gain_db=0.0, allow_nearby_same_sign=True,
                max_freq_hz=max_freq_hz, low_freq_q_cap=low_cap, max_boost_db=max_boost_db,
            )
        if candidate is None:
            break
        bands.append(candidate)
    if len(bands) >= 2:
        bands = _refine_bands_jointly(objective, bands, max_gain_db=max_gain_db, max_q=max_q, max_freq_hz=max_freq_hz, max_boost_db=max_boost_db)
    return bands
```

Note on shelves: `_edge_shelf_candidate` gain is clamped to `±max_gain_db`. For the room caller, the boost ceiling is enforced on shelves by the safety clamp in `fit_room_bands` (Task 4); a low-shelf is rarely a *boost* in the bass-cut-dominated room case, so this is not a practical gap, but the Task 4 safety clamp covers it regardless.

Note: the `shelf_candidates` block stays as-is. With a sub-cutoff target the high-shelf candidate (needs `freqs >= 7000`) cannot trigger; a low shelf at 105 Hz is acceptable for broadband bass tilt. Room callers also pass a sub-cutoff frequency slice (Task 4), so shelves stay within band.

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_peq_room_constraints.py tests/test_peq.py -q`
Expected: PASS (new constraints hold; existing `test_peq.py` still green).

- [ ] **Step 8: Commit**

```bash
git add headmatch/peq.py tests/test_peq_room_constraints.py
git commit -m "feat(peq): add band-limit, low-freq Q-cap, and asymmetric boost-ceiling options for room fitting"
```

---

### Task 4: Room target + room-fit orchestration (`room.py`)

**Files:**
- Create: `headmatch/room.py`
- Test: `tests/test_room.py`

**Interfaces:**
- Consumes: `analyze_room_measurement` (Task 2), `fit_peq(..., max_freq_hz, low_freq_q_cap)` (Task 3), `mic_cal.load_mic_calibration`/`calibration_offset` (Task 1), `geometric_log_grid`, `peq_chain_response_db`, `assess_eq_clipping`, `summarize_trustworthiness`, exporters, `render_fit_graphs` (Task 5 adds `cutoff_hz`), `MeasurementResult`, `TargetCurve`, `ConfidenceSummary`, `save_fr_csv`, `save_json`, `get_app_identity`.
- Produces:
  - Constants `ROOM_CUTOFF_DEFAULT_HZ = 300.0`, `ROOM_MAX_BOOST_DB = 2.0`, `ROOM_MAX_CUT_DB = 12.0`, `ROOM_SUBBASS_ROLLOFF_HZ = 40.0`, `ROOM_SUBBASS_ROLLOFF_DB = 3.0`.
  - `build_room_target(freqs_hz: np.ndarray) -> TargetCurve` — flat 0 dB above the rolloff knee, tilting down to `-ROOM_SUBBASS_ROLLOFF_DB` at 20 Hz.
  - `fit_room_bands(result: MeasurementResult, target: TargetCurve, sample_rate: int, *, cutoff_hz: float, max_filters: int) -> tuple[list[PEQBand], dict]` — pure core: returns bands + a report dict.
  - `run_room_fit(recording: str|Path, *, recording_two=None, mic_cal=None, cutoff_hz=ROOM_CUTOFF_DEFAULT_HZ, target_csv=None, max_filters=8, out_dir, sweep_spec) -> dict` — full offline path, writes artifacts, returns the run-summary dict.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_room.py
from __future__ import annotations

import json

import numpy as np
import pytest

from headmatch.analysis import MeasurementResult
from headmatch.peq import peq_chain_response_db
from headmatch.room import (
    ROOM_CUTOFF_DEFAULT_HZ,
    ROOM_MAX_BOOST_DB,
    build_room_target,
    fit_room_bands,
    run_room_fit,
)
from headmatch.signals import SweepSpec, generate_log_sweep, geometric_log_grid
from headmatch.io_utils import write_wav


def _mono_result(values_db):
    grid = geometric_log_grid(20, 20000, 48)
    v = np.asarray(values_db, dtype=np.float64)
    return MeasurementResult(grid, v, v.copy(), v.copy(), v.copy(), {
        'alignment_reference_score': 0.99, 'alignment_peak_ratio': 0.99,
        'channel_mismatch_rms_db': 0.0, 'left_roughness_db': 0.1,
        'right_roughness_db': 0.1, 'capture_rms_dbfs': -20.0,
    })


def test_room_target_flat_above_knee_and_rolls_off_sub_bass():
    grid = geometric_log_grid(20, 20000, 48)
    target = build_room_target(grid)
    assert float(np.interp(100.0, grid, target.values_db)) == 0.0
    assert float(np.interp(20.0, grid, target.values_db)) < -2.0
    assert target.semantics == 'absolute'


def test_room_target_knee_is_flat_at_40_hz():
    # The rolloff must START at the knee: 0 dB at exactly ROOM_SUBBASS_ROLLOFF_HZ.
    grid = geometric_log_grid(20, 20000, 48)
    target = build_room_target(grid)
    assert abs(float(np.interp(40.0, grid, target.values_db))) < 0.01


def test_fit_places_no_band_above_cutoff():
    grid = geometric_log_grid(20, 20000, 48)
    # +5 dB hump at 2 kHz (above cutoff) + +6 dB mode at 55 Hz (in band)
    measured = (5.0 * np.exp(-0.5 * (np.log2(grid / 2000.0) / 0.25) ** 2)
                + 6.0 * np.exp(-0.5 * (np.log2(grid / 55.0) / 0.15) ** 2))
    result = _mono_result(measured)
    bands, report = fit_room_bands(result, build_room_target(grid), 48000,
                                   cutoff_hz=ROOM_CUTOFF_DEFAULT_HZ, max_filters=8)
    assert bands, "expected at least one corrective band"
    assert all(b.freq <= ROOM_CUTOFF_DEFAULT_HZ + 1e-6 for b in bands)


def test_hard_boost_ceiling_on_deep_null():
    grid = geometric_log_grid(20, 20000, 48)
    measured = -15.0 * np.exp(-0.5 * (np.log2(grid / 80.0) / 0.1) ** 2)  # deep null at 80 Hz
    result = _mono_result(measured)
    bands, report = fit_room_bands(result, build_room_target(grid), 48000,
                                   cutoff_hz=ROOM_CUTOFF_DEFAULT_HZ, max_filters=8)
    assert all(b.gain_db <= ROOM_MAX_BOOST_DB + 1e-6 for b in bands)


def test_boost_ceiling_holds_with_multiple_nulls_through_joint_refinement():
    # Two deep nulls each "want" a large boost; joint Nelder-Mead refinement runs
    # with >=2 peaking bands, so this exercises the structural max_boost_db path.
    grid = geometric_log_grid(20, 20000, 48)
    measured = (-12.0 * np.exp(-0.5 * (np.log2(grid / 60.0) / 0.1) ** 2)
                + -12.0 * np.exp(-0.5 * (np.log2(grid / 95.0) / 0.1) ** 2))
    result = _mono_result(measured)
    bands, report = fit_room_bands(result, build_room_target(grid), 48000,
                                   cutoff_hz=ROOM_CUTOFF_DEFAULT_HZ, max_filters=8)
    assert all(b.gain_db <= ROOM_MAX_BOOST_DB + 1e-6 for b in bands)


def test_corrects_in_band_mode_with_a_cut():
    grid = geometric_log_grid(20, 20000, 48)
    measured = 6.0 * np.exp(-0.5 * (np.log2(grid / 60.0) / 0.13) ** 2)  # +6 dB mode at 60 Hz
    result = _mono_result(measured)
    bands, report = fit_room_bands(result, build_room_target(grid), 48000,
                                   cutoff_hz=ROOM_CUTOFF_DEFAULT_HZ, max_filters=8)
    cuts = [b for b in bands if b.gain_db < 0 and 40 < b.freq < 90]
    assert cuts, "expected a corrective cut near 60 Hz"
    # The cut should meaningfully reduce the 60 Hz peak.
    corrected = measured + peq_chain_response_db(grid, 48000, bands)
    assert float(np.interp(60.0, grid, corrected)) < 4.0


def _write_room_wav(tmp_path):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    _, mono = generate_log_sweep(spec)
    pre = np.zeros(int(spec.pre_silence_s * spec.sample_rate))
    post = np.zeros(int(spec.post_silence_s * spec.sample_rate))
    write_wav(tmp_path / "room.wav", np.concatenate([pre, mono, post]).reshape(-1, 1), spec.sample_rate)
    return tmp_path / "room.wav", spec


def test_run_room_fit_writes_all_artifacts_and_marks_missing_cal(tmp_path):
    rec, spec = _write_room_wav(tmp_path)
    out = tmp_path / "out"
    summary = run_room_fit(rec, mic_cal=None, out_dir=out, sweep_spec=spec)
    for name in ("equalizer_apo.txt", "camilladsp_full.yaml", "camilladsp_filters_only.yaml",
                 "room_fr.csv", "target_curve.csv", "run_summary.json", "README.txt"):
        assert (out / name).exists(), f"missing {name}"
    data = json.loads((out / "run_summary.json").read_text())
    assert data["target"].startswith("room")
    # Missing calibration must be surfaced as a warning and penalise confidence.
    assert any("calibrat" in w.lower() for w in data["confidence"]["warnings"])
    assert data["confidence"]["metrics"]["mic_cal_applied"] == 0.0


def test_run_room_fit_rejects_missing_second_recording(tmp_path):
    rec, spec = _write_room_wav(tmp_path)
    with pytest.raises(FileNotFoundError):
        run_room_fit(rec, recording_two=tmp_path / "nope.wav",
                     out_dir=tmp_path / "out", sweep_spec=spec)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_room.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'headmatch.room'`.

- [ ] **Step 3: Write the implementation**

```python
# headmatch/room.py
"""Room measurement & bass-only modal correction.

Measures a speaker-in-room response with a calibrated USB mic and fits a
corrective EQ restricted to the modal region (<= cutoff). Reuses the existing
analysis, fitting, export, and confidence machinery; the only room-specific
logic lives here and in mic_cal.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis import MeasurementResult, analyze_room_measurement
from .app_identity import get_app_identity
from .contracts import (
    RUN_SUMMARY_SCHEMA_VERSION,
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
)
from .eq_clipping import assess_eq_clipping
from .exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_parametric_txt,
)
from .io_utils import save_fr_csv, save_json
from .mic_cal import calibration_offset, load_mic_calibration
from .peq import PEQBand, peq_chain_response_db, fit_peq
from .plots import render_fit_graphs
from .pipeline_confidence import summarize_trustworthiness
from .signals import SweepSpec
from .targets import TargetCurve, load_curve, resample_curve

ROOM_CUTOFF_DEFAULT_HZ = 300.0
ROOM_MAX_BOOST_DB = 2.0
ROOM_MAX_CUT_DB = 12.0
# Q ceiling for modal cuts. 8.0 resolves real room modes (a 40 Hz mode at Q=8 has
# ~5 Hz bandwidth) while staying clear of the coefficient-precision regime where a
# 40 Hz / Q=12 biquad at 48 kHz gets sensitive (review finding: keep Q<=~8 below 50 Hz
# so presets remain safe even outside double-precision rendering).
ROOM_MAX_Q = 8.0
ROOM_SUBBASS_ROLLOFF_HZ = 40.0
ROOM_SUBBASS_ROLLOFF_DB = 3.0


def build_room_target(freqs_hz: np.ndarray) -> TargetCurve:
    """Flat (0 dB) above the rolloff knee; tilt down to -ROOM_SUBBASS_ROLLOFF_DB at 20 Hz."""
    freqs = np.asarray(freqs_hz, dtype=np.float64)
    values = np.zeros_like(freqs)
    knee = ROOM_SUBBASS_ROLLOFF_HZ
    low = freqs < knee
    if np.any(low):
        # Linear in log-frequency from 0 dB at the knee to -rolloff at 20 Hz.
        span = np.log2(knee / 20.0)
        frac = np.clip(np.log2(knee / np.maximum(freqs, 1.0)) / max(span, 1e-9), 0.0, 1.0)
        values = np.where(low, -ROOM_SUBBASS_ROLLOFF_DB * frac, values)
    return TargetCurve(freqs_hz=freqs, values_db=values, name='room_flat', semantics='absolute')


def fit_room_bands(
    result: MeasurementResult,
    target: TargetCurve,
    sample_rate: int,
    *,
    cutoff_hz: float,
    max_filters: int,
) -> tuple[list[PEQBand], dict]:
    """Pure fit core: band-limited, boost-capped, high-Q modal correction."""
    freqs = result.freqs_hz
    target_resampled = resample_curve(target, freqs)
    measured = result.left_db  # mono: left == right
    eq_target = target_resampled.values_db - measured
    # Reduce demand up front: never ask the fitter for more than the boost ceiling.
    eq_target_capped = np.minimum(eq_target, ROOM_MAX_BOOST_DB)

    # The boost ceiling is enforced STRUCTURALLY via max_boost_db — greedy placement
    # and joint Nelder-Mead refinement both clamp positive gain to ROOM_MAX_BOOST_DB,
    # so the optimizer never explores gains it would later have to clamp away.
    bands = fit_peq(
        freqs, eq_target_capped, sample_rate,
        max_filters=max_filters, max_gain_db=ROOM_MAX_CUT_DB, max_q=ROOM_MAX_Q,
        max_freq_hz=cutoff_hz, low_freq_q_cap=ROOM_MAX_Q, max_boost_db=ROOM_MAX_BOOST_DB,
    )
    # Belt-and-suspenders: also covers shelf bands, which fit_peq clamps to ±max_gain_db.
    for b in bands:
        if b.gain_db > ROOM_MAX_BOOST_DB:
            b.gain_db = ROOM_MAX_BOOST_DB

    predicted = measured + peq_chain_response_db(freqs, sample_rate, bands)
    band_mask = freqs <= cutoff_hz
    err = (predicted - target_resampled.values_db)[band_mask]
    rms = float(np.sqrt(np.mean(err ** 2))) if err.size else 0.0
    max_abs = float(np.max(np.abs(err))) if err.size else 0.0

    clip = assess_eq_clipping(freqs, sample_rate, bands, bands)
    report = {
        'generated_by': get_app_identity().as_metadata(),
        'mode': 'room',
        'cutoff_hz': float(cutoff_hz),
        'predicted_left_rms_error_db': rms,
        'predicted_right_rms_error_db': rms,
        'predicted_left_max_error_db': max_abs,
        'predicted_right_max_error_db': max_abs,
        'measurement_diagnostics': result.diagnostics,
        'eq_clipping': {
            'will_clip': clip.will_clip,
            'left_peak_boost_db': clip.left_peak_boost_db,
            'right_peak_boost_db': clip.right_peak_boost_db,
            'preamp_db': clip.total_preamp_db,
            'headroom_loss_db': clip.headroom_loss_db,
            'quality_concern': clip.quality_concern,
        },
        'bands': [b.__dict__ for b in bands],
    }
    return bands, report


def _room_confidence(result: MeasurementResult, report: dict, *, mic_cal_applied: bool, cutoff_hz: float) -> ConfidenceSummary:
    base = summarize_trustworthiness(result, report)
    warnings = list(base.warnings)
    score = base.score
    warnings.append(
        f"Modal correction only (<= {cutoff_hz:.0f} Hz); the response above the cutoff is shown "
        "but not equalised — minimum-phase EQ cannot fix reflections there."
    )
    warnings.append(
        "Measured at a single seat: a dip here may be a seat-specific null, not a room-wide "
        "problem. Re-run with a second position (--listen-position-two) to improve this."
    )
    warnings.append("Sub-bass below ~30 Hz is room/level/mic limited and should be treated as low-confidence.")
    if not mic_cal_applied:
        warnings.append(
            "No microphone calibration file was supplied — the mic's own response is baked into "
            "the result. Supply --mic-cal for a trustworthy room measurement."
        )
        score = max(0, score - 25)
    label = 'high' if score >= 85 else 'medium' if score >= 65 else 'low'
    metrics = dict(base.metrics)
    metrics['mic_cal_applied'] = 1.0 if mic_cal_applied else 0.0
    metrics['cutoff_hz'] = float(cutoff_hz)
    return ConfidenceSummary(
        score=score, label=label, headline=base.headline, interpretation=base.interpretation,
        reasons=base.reasons, warnings=tuple(warnings), metrics=metrics,
    )


def _apply_calibration(result: MeasurementResult, mic_cal: str | Path | None) -> bool:
    if mic_cal is None:
        return False
    cal = load_mic_calibration(mic_cal)
    offset = calibration_offset(cal, result.freqs_hz)
    result.left_db = result.left_db + offset
    result.right_db = result.right_db + offset
    result.left_raw_db = result.left_raw_db + offset
    result.right_raw_db = result.right_raw_db + offset
    return True


def _average_two(a: MeasurementResult, b: MeasurementResult) -> MeasurementResult:
    """Energy-average two mono measurements in the magnitude (dB) domain."""
    left = 0.5 * (a.left_db + b.left_db)
    raw = 0.5 * (a.left_raw_db + b.left_raw_db)
    diag = {k: 0.5 * (a.diagnostics.get(k, 0.0) + b.diagnostics.get(k, 0.0)) for k in a.diagnostics}
    return MeasurementResult(a.freqs_hz, left, left.copy(), raw, raw.copy(), diag)


def _write_room_readme(out_dir: Path, confidence: ConfidenceSummary, cutoff_hz: float) -> None:
    lines = [
        "headmatch room-fit results",
        "==========================",
        "",
        "Bass-only room correction. EQ is applied ONLY below the cutoff "
        f"({cutoff_hz:.0f} Hz), where the room behaves minimum-phase and EQ works.",
        "The response above the cutoff is measured and graphed but deliberately not equalised.",
        "",
        f"Confidence: {confidence.label} ({confidence.score}/100) — {confidence.headline}",
        "",
        "Caveats",
        "-------",
    ]
    lines += [f"- {w}" for w in confidence.warnings]
    lines += [
        "",
        "Files",
        "-----",
        "- equalizer_apo.txt: Equalizer APO parametric preset (same EQ on both channels).",
        "- camilladsp_full.yaml / camilladsp_filters_only.yaml: CamillaDSP configs.",
        "- room_fr.csv: corrected, full-range in-room response.",
        "- target_curve.csv: the room target used for fitting.",
        "- fit_overview.svg / fit_left.svg / fit_right.svg: review graphs (cutoff marked).",
        "- run_summary.json: machine-readable summary, confidence, and clipping.",
        "",
        "Note: the speaker's own response is part of the measurement and is not separated out.",
    ]
    (out_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_room_fit(
    recording: str | Path,
    *,
    recording_two: str | Path | None = None,
    mic_cal: str | Path | None = None,
    cutoff_hz: float = ROOM_CUTOFF_DEFAULT_HZ,
    target_csv: str | Path | None = None,
    max_filters: int = 8,
    out_dir: str | Path,
    sweep_spec: SweepSpec,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = analyze_room_measurement(recording, sweep_spec)
    if recording_two is not None:
        if not Path(recording_two).exists():
            raise FileNotFoundError(f"Second recording not found: {recording_two}")
        result = _average_two(result, analyze_room_measurement(recording_two, sweep_spec))
    mic_cal_applied = _apply_calibration(result, mic_cal)

    target = load_curve(target_csv) if target_csv else build_room_target(result.freqs_hz)
    bands, report = fit_room_bands(result, target, sweep_spec.sample_rate, cutoff_hz=cutoff_hz, max_filters=max_filters)
    confidence = _room_confidence(result, report, mic_cal_applied=mic_cal_applied, cutoff_hz=cutoff_hz)

    clip = report['eq_clipping']
    export_equalizer_apo_parametric_txt(
        out_dir / 'equalizer_apo.txt', bands, bands,
        preamp_db=(float(clip['preamp_db']) if clip['will_clip'] else None),
    )
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', bands, bands, samplerate=sweep_spec.sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', bands, bands)
    save_fr_csv(out_dir / 'room_fr.csv', result.freqs_hz, result.left_db)

    target_resampled = resample_curve(target, result.freqs_hz)
    save_fr_csv(out_dir / 'target_curve.csv', result.freqs_hz, target_resampled.values_db, column_name='target_db')
    render_fit_graphs(out_dir, result, target, sweep_spec.sample_rate, bands, bands, cutoff_hz=cutoff_hz)

    summary = FrontendRunSummary(
        schema_version=RUN_SUMMARY_SCHEMA_VERSION,
        generated_by=get_app_identity().as_metadata(),
        kind='fit',
        out_dir=str(out_dir),
        sample_rate=sweep_spec.sample_rate,
        frequency_points=int(len(result.freqs_hz)),
        target=target.name,
        filters=RunFilterCounts(left=len(bands), right=len(bands)),
        predicted_error_db=RunErrorSummary(
            left_rms=report['predicted_left_rms_error_db'],
            right_rms=report['predicted_right_rms_error_db'],
            left_max=report['predicted_left_max_error_db'],
            right_max=report['predicted_right_max_error_db'],
        ),
        confidence=confidence,
        plots={'overview': str(out_dir / 'fit_overview.svg')},
        results_guide=str(out_dir / 'README.txt'),
        filter_budget=None,
        eq_clipping_assessment=report['eq_clipping'],
    )
    save_json(out_dir / 'fit_report.json', report)
    save_json(out_dir / 'run_summary.json', summary.to_dict())
    _write_room_readme(out_dir, confidence, cutoff_hz)
    return summary.to_dict()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_room.py -q`
Expected: PASS (6 tests). (Requires Task 5's `cutoff_hz` parameter on `render_fit_graphs`; if running Task 4 before Task 5, temporarily drop the `cutoff_hz=` kwarg from the `render_fit_graphs` call, then restore it in Task 5. Prefer implementing Task 5 first.)

- [ ] **Step 5: Commit**

```bash
git add headmatch/room.py tests/test_room.py
git commit -m "feat(room): add room target and bass-only modal-correction fit orchestration"
```

---

### Task 5: Cutoff marker in review graphs (`plots.py`)

**Files:**
- Modify: `headmatch/plots.py` — `render_fit_graphs`
- Test: `tests/test_plots_room.py`

**Interfaces:**
- Consumes: existing plot helpers.
- Produces: `render_fit_graphs(..., cutoff_hz: float | None = None)` — when set, draws a labelled vertical marker at `cutoff_hz` on each panel; default `None` preserves current output exactly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plots_room.py
from __future__ import annotations

import numpy as np

from headmatch.analysis import MeasurementResult
from headmatch.plots import render_fit_graphs
from headmatch.signals import geometric_log_grid
from headmatch.targets import create_flat_target


def _result():
    grid = geometric_log_grid(20, 20000, 48)
    z = np.zeros_like(grid)
    return MeasurementResult(grid, z, z.copy(), z.copy(), z.copy(), {})


def test_cutoff_marker_present_when_requested(tmp_path):
    res = _result()
    paths = render_fit_graphs(tmp_path, res, create_flat_target(res.freqs_hz), 48000, [], [], cutoff_hz=300.0)
    svg = (tmp_path / "fit_overview.svg").read_text()
    assert "EQ region" in svg or "cutoff" in svg.lower()


def test_no_marker_by_default(tmp_path):
    res = _result()
    render_fit_graphs(tmp_path, res, create_flat_target(res.freqs_hz), 48000, [], [])
    svg = (tmp_path / "fit_overview.svg").read_text()
    assert "EQ region" not in svg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plots_room.py -q`
Expected: FAIL — `render_fit_graphs() got an unexpected keyword argument 'cutoff_hz'`.

- [ ] **Step 3: Implement the marker**

In `plots.py`, add a helper and thread the parameter:

```python
def _cutoff_marker(cutoff_hz: float, freqs: np.ndarray, x: float, y: float, w: float, h: float) -> list[str]:
    if cutoff_hz < freqs[0] or cutoff_hz > freqs[-1]:
        return []
    cx = float(_log_x_positions(np.array([cutoff_hz], dtype=np.float64), w, domain=freqs)[0] + x)
    return [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{cx - x:.2f}" height="{h:.2f}" fill="#16a34a" fill-opacity="0.06" />',
        f'<line x1="{cx:.2f}" y1="{y:.2f}" x2="{cx:.2f}" y2="{y + h:.2f}" stroke="#16a34a" stroke-width="1.5" stroke-dasharray="5 4" />',
        f'<text class="small" x="{cx + 4:.2f}" y="{y + 14:.2f}" fill="#15803d">EQ region &#8804; {cutoff_hz:.0f} Hz</text>',
    ]
```

Change the `render_fit_graphs` signature to accept `cutoff_hz: float | None = None`, and after each `_draw_panel(...)` call append the marker. Simplest approach: wrap the panel extends. For the overview's two panels (at y=80 and y=390) and each per-side panel (y=80), add:

```python
    if cutoff_hz is not None:
        overview_body.extend(_cutoff_marker(cutoff_hz, freqs, 70, 80, 1030, 250))
        overview_body.extend(_cutoff_marker(cutoff_hz, freqs, 70, 390, 1030, 250))
```

and inside the per-side loop, after `body.extend(_draw_panel(...))`:

```python
        if cutoff_hz is not None:
            body.extend(_cutoff_marker(cutoff_hz, freqs, 70, 80, 1030, 250))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_plots_room.py tests/test_plots.py -q`
Expected: PASS (new marker present when requested; existing plot tests still green).

- [ ] **Step 5: Commit**

```bash
git add headmatch/plots.py tests/test_plots_room.py
git commit -m "feat(plots): mark the corrected band region on room review graphs"
```

---

### Task 6: CLI wiring + config + doctor (`cli.py`, `contracts.py`, `measure.py`)

**Files:**
- Modify: `headmatch/contracts.py` — add `"room"` to `WorkflowName`; add `preferred_mic_cal_csv` field to `FrontendConfig`
- Modify: `headmatch/cli.py` — `build_parser` (two subparsers) + `main` dispatch
- Modify: `headmatch/measure.py` — `collect_doctor_checks` adds a mic-cal check
- Test: `tests/test_room_cli.py`

**Interfaces:**
- Consumes: `run_room_fit`, `run_pipewire_measurement`, `MeasurementPaths`, `PipeWireDeviceConfig`, `spec_from_args`, `add_common_sweep_args`.
- Produces: `headmatch room-measure` and `headmatch room-fit` commands.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_room_cli.py
from __future__ import annotations

import json

import numpy as np

from headmatch.cli import main
from headmatch.io_utils import write_wav
from headmatch.signals import SweepSpec, generate_log_sweep


def _write_room_wav(path):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    _, mono = generate_log_sweep(spec)
    pre = np.zeros(int(spec.pre_silence_s * spec.sample_rate))
    post = np.zeros(int(spec.post_silence_s * spec.sample_rate))
    write_wav(path, np.concatenate([pre, mono, post]).reshape(-1, 1), spec.sample_rate)


def test_room_fit_cli_writes_summary(tmp_path):
    rec = tmp_path / "room.wav"
    _write_room_wav(rec)
    out = tmp_path / "out"
    main([
        "--config", str(tmp_path / "config.json"),
        "room-fit", "--recording", str(rec), "--out-dir", str(out),
        "--duration", "1.0", "--pre-silence", "0.1", "--post-silence", "0.2",
        "--cutoff-hz", "250",
    ])
    summary = json.loads((out / "run_summary.json").read_text())
    assert summary["confidence"]["metrics"]["cutoff_hz"] == 250.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_room_cli.py -q`
Expected: FAIL — argparse error: invalid choice `room-fit` (or `SystemExit`).

- [ ] **Step 3: Extend `WorkflowName` and `FrontendConfig`**

In `contracts.py`, add `"room"` to the `WorkflowName` literal list (after `"hearing-fit"`), and add a field to `FrontendConfig` (after `preferred_target_csv`):

```python
    preferred_mic_cal_csv: Optional[str] = None
```

- [ ] **Step 4: Add the subparsers**

In `cli.py` `build_parser`, after the `hearing-fit` parser block, add:

```python
    p = sub.add_parser("room-fit", help="Fit a bass-only room correction from a recorded sweep (calibrated mic).")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--recording-two", default=None, help="Optional second seat-position recording, energy-averaged with the first.")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--mic-cal", default=config.preferred_mic_cal_csv, help="Microphone calibration CSV (UMIK-1 style). Strongly recommended.")
    p.add_argument("--cutoff-hz", type=float, default=300.0, help="Upper limit of the corrected (modal) band. Default 300 Hz.")
    p.add_argument("--max-filters", type=int, default=config.max_filters)

    p = sub.add_parser("room-measure", help="Play a sweep through a speaker and record it at the seat, then fit a room correction.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--output-target", default=config.pipewire_output_target)
    p.add_argument("--input-target", default=config.pipewire_input_target)
    p.add_argument("--mic-cal", default=config.preferred_mic_cal_csv, help="Microphone calibration CSV (UMIK-1 style). Strongly recommended.")
    p.add_argument("--listen-position-two", action="store_true", help="Capture a second seat position and energy-average the two.")
    p.add_argument("--cutoff-hz", type=float, default=300.0)
    p.add_argument("--max-filters", type=int, default=config.max_filters)
```

- [ ] **Step 5: Add dispatch branches**

In `cli.py` `main`, add `run_room_fit` to the `from .room import ...` (add a new import line near the other workflow imports) and add branches alongside the existing `elif args.cmd == ...` chain:

```python
        elif args.cmd == "room-fit":
            from .room import run_room_fit
            run_room_fit(
                args.recording,
                recording_two=args.recording_two,
                mic_cal=args.mic_cal,
                cutoff_hz=args.cutoff_hz,
                max_filters=args.max_filters,
                out_dir=args.out_dir,
                sweep_spec=spec_from_args(args),
            )
        elif args.cmd == "room-measure":
            from .room import run_room_fit
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            spec = spec_from_args(args)
            rec1 = out_dir / "recording.wav"
            run_pipewire_measurement(spec, MeasurementPaths(out_dir / "sweep.wav", rec1),
                                     PipeWireDeviceConfig(output_target=args.output_target, input_target=args.input_target))
            rec2 = None
            if args.listen_position_two:
                print("Reposition the mic to the second seat position, then press Enter...")
                input()
                rec2 = out_dir / "recording_pos2.wav"
                run_pipewire_measurement(spec, MeasurementPaths(out_dir / "sweep2.wav", rec2),
                                         PipeWireDeviceConfig(output_target=args.output_target, input_target=args.input_target))
            run_room_fit(rec1, recording_two=rec2, mic_cal=args.mic_cal,
                         cutoff_hz=args.cutoff_hz, max_filters=args.max_filters,
                         out_dir=out_dir, sweep_spec=spec)
```

- [ ] **Step 6: Add the doctor mic-cal check**

In `measure.py` `collect_doctor_checks`, before the final `return checks`, add:

```python
    cal = getattr(config, "preferred_mic_cal_csv", None)
    if cal:
        cal_path = Path(cal)
        checks.append(DoctorCheck(
            name="room mic calibration",
            ok=cal_path.exists(),
            detail=f"Configured: {cal}" if cal_path.exists() else f"Configured but missing: {cal}",
            action=None if cal_path.exists() else "Point --mic-cal at your UMIK-1 calibration CSV, or re-save the config.",
        ))
    else:
        checks.append(DoctorCheck(
            name="room mic calibration",
            ok=True,
            detail="No mic calibration saved (only needed for room-measure / room-fit).",
            action="Pass --mic-cal to room commands; uncalibrated room measurements are low-confidence.",
        ))
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_room_cli.py tests/test_cli.py -q`
Expected: PASS (room commands work; existing CLI tests still green).

- [ ] **Step 8: Commit**

```bash
git add headmatch/cli.py headmatch/contracts.py headmatch/measure.py tests/test_room_cli.py
git commit -m "feat(room): wire room-measure/room-fit CLI, config field, and doctor check"
```

---

### Task 7: Example house-curve CSVs + docs

**Files:**
- Create: `docs/examples/targets/room_flat.csv`
- Create: `docs/examples/targets/room_house_tilt.csv`
- Modify: `docs/examples/targets/README.md` (mention the two room targets)
- Modify: `README.md` (add a short "Room measurement (beta)" section under the workflow table)

**Interfaces:** none (data + docs).

- [ ] **Step 1: Write `room_flat.csv`**

```
# headmatch_target_semantics=absolute
# Flat in-room target: 0 dB across the band. Use as the room-fit target for a neutral seat response.
frequency_hz,target_db
20,0.0
1000,0.0
20000,0.0
```

- [ ] **Step 2: Write `room_house_tilt.csv`**

```
# headmatch_target_semantics=absolute
# Gentle in-room "house curve": flat bass, ~-1 dB/octave downward tilt above 1 kHz.
# Used for the review-graph overlay above the correction cutoff.
frequency_hz,target_db
20,0.0
1000,0.0
2000,-1.0
4000,-2.0
8000,-3.0
20000,-5.0
```

- [ ] **Step 3: Verify both load**

Run: `python -c "from headmatch.targets import load_curve; print(load_curve('docs/examples/targets/room_flat.csv').name); print(load_curve('docs/examples/targets/room_house_tilt.csv').name)"`
Expected: prints `room_flat` and `room_house_tilt` with no error.

- [ ] **Step 4: Update the docs**

Add to `docs/examples/targets/README.md`: a bullet for `room_flat.csv` and `room_house_tilt.csv` describing them as room-fit targets/overlays.
Add to `README.md` a short "Room measurement (beta)" subsection: what it does (bass-only correction ≤300 Hz with a calibrated USB mic), the two commands (`room-measure`, `room-fit`), and the single-point / calibration caveats.

- [ ] **Step 5: Commit**

```bash
git add docs/examples/targets/room_flat.csv docs/examples/targets/room_house_tilt.csv docs/examples/targets/README.md README.md
git commit -m "docs(room): add example room targets and document the room workflow"
```

---

## Final verification

- [ ] Run the full suite: `python -m pytest -q` — all tests green.
- [ ] Run mypy if configured: `python -m mypy headmatch` — no new errors (the codebase has a mypy CI step since 0.7.1).
- [ ] Manual smoke (optional): generate a sweep, record it, and run `headmatch room-fit --recording rec.wav --mic-cal umik.csv --out-dir out` — confirm `out/` contains the EQ presets, `room_fr.csv`, a cutoff-marked SVG, and a `run_summary.json` whose confidence warnings mention the single-point and calibration caveats.

---

## Self-review notes (spec coverage)

- §2 two-position average → Task 4 `_average_two` + Task 6 `--listen-position-two` / `--recording-two`. ✅
- §3.1 `mic_cal.py` (relative-only, scale + coverage guards, tolerant parsing, phase ignored) → Task 1. ✅
- §3.1 `room.py` (band-limit, hard boost ceiling, Q floor, clipping pre-finalization) → Task 3 (peq options) + Task 4 (`fit_room_bands`). ✅ Boost ceiling is **structural** (`max_boost_db` clamps greedy placement *and* joint refinement), with a belt-and-suspenders post-clamp for shelves.
- §3.2 reuse of analysis/exporters/confidence → Tasks 2 & 4. ✅
- §3.3 USB-mic alignment latency tolerance → Task 2 `test_alignment_tolerates_large_round_trip_latency`. ✅
- §4.2 grid density for narrow modes → reuse of 48-ppo `geometric_log_grid`; high-Q fitting in Task 3. ✅
- §5 room target + sub-bass rolloff + speaker-FR-not-separated note → Task 4 `build_room_target` + README. ✅
- §7 CLI (`room-measure` live / `room-fit` offline split) → Task 6. ✅
- §8 export Q convention (APO vs CamillaDSP) → reuse of existing `exporters.py` (each emits its own convention); both fed the same band set. ✅
- §8 shaded ≤cutoff region in the SVG → Task 5. ✅
- §9 confidence caveats (single-point, sub-bass, missing-cal penalty) → Task 4 `_room_confidence`. ✅
- §12 resolved decisions (300 Hz default, soft block on missing cal, ship two example CSVs) → Tasks 4/6/7. ✅

## Validation follow-ups applied (companion architectural-review of this plan)

1. **Structural boost ceiling** — `max_boost_db` threaded through `fit_peq` → `_peaking_candidate` → `_refine_bands_jointly`; the optimizer respects +2 dB rather than relying on a post-hoc clamp. New tests: `test_asymmetric_boost_cap_survives_joint_refinement` (Task 3), `test_boost_ceiling_holds_with_multiple_nulls_through_joint_refinement` (Task 4).
2. **Conservative low-frequency Q** — room Q ceiling lowered from 12 to `ROOM_MAX_Q = 8.0` (safe biquad coefficients at 40 Hz / 48 kHz beyond double precision), with rationale comment.
3. **Explicit execution order** — `1 → 2 → 3 → 5 → 4 → 6 → 7` stated in Global Constraints.
4. **Extra guards/tests** — `recording_two` existence guard (`test_run_room_fit_rejects_missing_second_recording`); knee-flat-at-40 Hz target test (`test_room_target_knee_is_flat_at_40_hz`). Also clarified the redundant `np.clip` in `_peaking_candidate` (defence-in-depth, unreachable when `max_freq_hz` is set).
```
