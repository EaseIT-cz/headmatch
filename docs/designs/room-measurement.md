# Design: Room measurement & modal correction

Status: **proposed** — not yet implemented. Implementation plan: `docs/tasks/TASK-117.md`.

Working name: `room-measure` / `room-fit`.

---

## 1. Summary

Add a new workflow that measures the **acoustic response of a room** (a speaker
playing into a room, captured at the listening seat with a portable, *calibrated*
USB microphone) and produces a **bass-only corrective EQ**.

This is the first HeadMatch feature aimed at **speakers in a room** rather than
headphones. It is explicitly anticipated in `docs/architecture.md` ("Likely future
work → Later → *Room correction / speaker measurement mode*"), so it extends the
product's stated direction rather than departing from it.

The measurement/fit **spine is reused verbatim** from the headphone pipeline. The
genuinely new work is narrow and bounded:

1. **Calibration in** — apply a measurement-mic calibration file to the estimated FR.
2. **Band-limited fit** — only place EQ filters in the modal region (≤ cutoff).
3. **Room target** — a flat-through-modal-band target instead of a headphone target.

Everything **above the cutoff is measured and graphed but never EQ'd**. Minimum-phase
EQ cannot fix reflections or comb-filtering; attempting full-range room "correction"
is the classic failure mode and is deliberately out of scope for the MVP.

---

## 2. MVP scope (decisions locked during brainstorming)

| Dimension | MVP choice | Notes |
|---|---|---|
| **Correction band** | Bass / modal only, **≤ ~300 Hz** (fixed default, configurable) | Above the cutoff: measure + graph, no filters. |
| **Microphone & sampling** | **Calibrated USB mic, single position** (primary seat) by default; **optional two-position average** via `--listen-position-two` | Single-point modal error is *not* fully averaged out — flagged prominently. The optional two-position energy-average catches the most egregious position-specific nulls at near-zero cost. Full multi-point (MMM) is Phase 2. |
| **Time domain** | **FR only** | No RT60 / impulse response in the MVP. Deferred to Phase 2. |
| **Channels** | **Mono corrective EQ** applied identically to both output channels | This means *mono EQ output*, not a mono capture. Bass is largely omnidirectional; one corrective EQ for the modal region applied to L and R is standard practice. Per-speaker stereo correction is Phase 2. |
| **Frontend** | **CLI + offline package first**, GUI fast-follow | Keeps the beta surface small; mirrors existing `measure`/`fit` split. |

### Why a fixed cutoff (not adaptive)

The Schroeder frequency — the boundary between the modal region (where EQ works) and
the statistical/reflective region (where it doesn't) — is derived from `RT60` and room
volume:

```
f_Schroeder ≈ 2000 · √(RT60 / V)
```

Because the MVP is **FR-only**, there is no measured `RT60` to compute this from. Using
a fixed, honest default (~300 Hz, configurable via `--cutoff-hz`) is the internally
consistent choice. Phase 2 (RT60 from the impulse response) makes the cutoff adaptive.

---

## 3. Architecture

### 3.1 New modules (2 files)

#### `headmatch/mic_cal.py`
The single most important correctness piece. Without it, the workflow would "correct"
the microphone's own response rather than the room.

**Calibration is relative-FR-only.** We apply the per-frequency gain *deviation* and
explicitly ignore absolute SPL. UMIK-1 cal files carry a sensitivity calibrator line
(e.g. `Sens Factor = -38.4 dB`); we parse past it and discard it — modal EQ does not
need absolute SPL. This is stated in the README and the `doctor` output so users aren't
surprised.

- **Parse tolerantly.** Accept UMIK-1-style CSVs and the common variants:
  comment/sensitivity header lines tolerated and ignored; `freq_hz,gain_db` data rows,
  whitespace-, comma-, **or tab-separated**; tolerate `Frequency(Hz),Magnitude(dB)`
  column-header lines.
- **Sanity-validate the scale.** A real calibration curve spans roughly ±a few dB, not
  ±50 dB. Reject (or loudly warn on) a file whose values are grossly out of that range —
  it's almost certainly a target/measurement CSV handed in by mistake, not a cal file.
- **Validate coverage.** The file must span at least **20 Hz – 500 Hz** (wider than the
  correction cutoff). Warn if it does not.
- **Phase data:** cal files are treated as magnitude-only. If a file carries a phase
  column (rare), it is ignored with a warning. Below 300 Hz mic phase is effectively
  minimum-phase, so this is safe for the MVP.
- PCHIP-interpolate the calibration curve onto the HeadMatch FR frequency grid
  (consistent with `target_editor.py`'s interpolation choice).
- Return an **additive dB offset** array aligned to the grid.
- Pure: no GUI, no audio, no filesystem coupling beyond reading the given path.

```python
def load_mic_calibration(path: Path) -> MicCalibration: ...
def calibration_offset(cal: MicCalibration, freq_grid: np.ndarray) -> np.ndarray:
    """dB offset per grid point; flat 0 dB outside the cal file's range (held, not extrapolated)."""
```

#### `headmatch/room.py`
Room-specific orchestration. Thin — leans on existing modules.

- Build the room/house target (flat through the modal band, with a defined sub-bass
  rolloff; see §5).
- Apply the mic-cal offset to the estimated in-room FR.
- Optionally energy-average two seat measurements before fitting (see §4.1).
- Invoke the existing PEQ fitter **constrained to f ≤ cutoff**, with:
  - a **hard boost ceiling** (default **+2 dB**, configurable down to 0) enforced as an
    *optimizer constraint*, not a soft L2 penalty — boosting room nulls is almost always
    wrong, so the fitter must be structurally unable to exceed the ceiling;
  - a **Q floor high enough for narrow modes** — room modes below 100 Hz can be sharp,
    so the fit must be *permitted* Q up to ~12. `peq.py`'s headphone defaults bias toward
    broad, low-Q filters; the room `FitObjective` must not inherit a Q cap that smooths
    narrow modal peaks away.
- Run the existing clipping/preamp predictor **before the fit is finalized**, so an
  over-aggressive cut set is caught up front rather than only reported post-hoc.
- Assemble artifacts via the shared `pipeline_artifacts.py` path.

```python
def run_room_fit(
    recording: Path,
    recording_two: Path | None,          # optional second seat position
    mic_cal: Path | None,
    cutoff_hz: float = ROOM_CUTOFF_DEFAULT_HZ,   # 300.0
    max_boost_db: float = ROOM_MAX_BOOST_DB,     # 2.0 (hard ceiling)
    target_csv: Path | None = None,
    out_dir: Path = ...,
) -> RunSummary: ...
```

### 3.2 Reused untouched

| Module | Reused for |
|---|---|
| `signals.py` | Log sweep generation (same stimulus works for rooms) |
| `backend_pipewire.py` / `backend_portaudio.py` | `play_and_record`: `output_target` = speaker, `input_target` = USB mic — maps cleanly to existing config fields |
| `analysis.py` | Cross-correlation alignment + Wiener-regularised FR estimation |
| `peq.py` | Fit, via injectable `FitObjective` weights + filter-budget (constrained band) |
| `exporters.py` | Equalizer APO + CamillaDSP export (unchanged) |
| `plots.py` | SVG review graph |
| `pipeline_confidence.py` | Trust scoring (with added room caveats) |
| `pipeline_artifacts.py` | Folder/README/summary contract |

### 3.3 Touched (small, additive)

| Module | Change |
|---|---|
| `contracts.py` | Add `"room"` to `WorkflowName`; add room summary fields (`cutoff_hz`, `mic_cal_applied`, `single_point: True`). |
| `cli.py` | Add `room-measure` and `room-fit` commands; doctor check for mic-cal presence. |
| `measure.py` | Reuse offline-package generation for the recorder-first room path (no behavioural change to headphone path). |
| `analysis.py` | **Verify alignment tolerates large round-trip latency.** Consumer USB mics have unadvertised hardware latency; the cross-correlation search must not rely on a hard-coded `expected_latency_samples` tuned for headphones (it could clip early energy). No code change expected if the search window is already generous — but this gets a dedicated test (§10). |
| `pipeline_confidence.py` | Add room-specific caveat text (single-point vs two-position, sub-bass unreliability, missing-cal penalty). |

---

## 4. Data flow

```
              ┌──────────────────────────────────────────────┐
   sweep ──── play/record (speaker out → USB mic in) ──▶ align ──▶ Wiener FR estimate
              └──────────────────────────────────────────────┘            │
                       (optional) second seat position ─── align ─── FR ───┤
                                                  energy-average if present │
                                                                           │ raw in-room FR
                          mic_cal.calibration_offset(grid) ────────────────┤ (full range)
                                                                           ▼
                                                          corrected in-room FR (full range)
                                                                           │
        room target (flat to cutoff, sub-bass rolloff) ──┐   band-limit: keep only f ≤ cutoff_hz
                                                          ▼
            fit_peq(band-limited, cuts-preferred, HARD boost ceiling, Q-floor for modes)
                                                          │
        EQ bands (≤ cutoff only) ──────────▶ Equalizer APO / CamillaDSP export
        full-range FR + house overlay + shaded EQ region ──────────▶ SVG review graph
        run_summary.json (workflow="room") + README.txt + confidence summary
```

The fitter sees a target that is flat across the modal band and is structurally
prevented from placing any filter above the cutoff. The full-range corrected FR is
still written and graphed so the user can *see* the reflective region without the tool
pretending to fix it.

### 4.1 Two-position averaging (optional)

When `--listen-position-two` (CLI) / a second recording is supplied, the two
measurements are **energy-averaged in the magnitude domain** before calibration and
fitting. This is cheap and catches the worst position-specific nulls (a deep dip present
at one seat position but not the other averages out rather than being aggressively
"corrected"). Default remains single-position. Full multi-point/MMM is Phase 2.

### 4.2 Frequency grid

Calibration offset and room FR **must share the same frequency grid**. The MVP uses the
existing HeadMatch log-spaced grid, but the grid must be dense enough at low frequencies
(sufficient points-per-octave below ~100 Hz) to resolve narrow room modes; a coarse grid
would smear a sharp mode and defeat the Q-floor described in §3.1. The chosen
points-per-octave is recorded in `run_summary.json`.

---

## 5. Room / house target

- **MVP target:** flat (0 dB) through the modal band, with a **defined sub-bass
  rolloff** at the bottom: the target tilts down by ~2–3 dB below **~40 Hz**. This
  prevents the fitter from chasing huge boosts into the region where the
  speaker/room/mic can't deliver clean output, and it keeps sub-bass correction sane.
  Because the MVP only EQs ≤ cutoff, the **in-band** target is otherwise flat — the
  fitter's job is to pull measured modal peaks toward flat (and, within the hard boost
  ceiling, lift only shallow dips).
- **Overlay-only house curve:** a gentle downward tilt above the cutoff (Harman-style
  in-room target). This is used **only for the review graph**, so the user can judge the
  uncorrected region against a sensible reference. Shipped as example CSVs alongside the
  existing `docs/examples/targets/` curves.
- **Speaker FR is not separated.** As with the headphone path, the measured response is
  speaker + room combined; the tool does not deconvolve a manufacturer/anechoic speaker
  curve. This is stated explicitly in the README so users don't expect speaker-only
  correction.

---

## 6. Key decisions & rationale

| Decision | Rationale |
|---|---|
| Fixed ~300 Hz cutoff (configurable) | FR-only MVP has no RT60 to derive Schroeder from; a fixed honest default is internally consistent. For typical domestic rooms (RT60 0.3–0.6 s, V 40–80 m³) Schroeder lands ~100–250 Hz, so 300 Hz is a safe-margin default. **Caveat:** large/live rooms (V > 150 m³, RT60 > 0.8 s) can push Schroeder below 100 Hz, where 300 Hz is too aggressive — `run_summary.json` logs a typical-room Schroeder estimate and the cutoff is configurable via `--cutoff-hz`. Optional room-dimensions input for a rough Schroeder estimate is a Phase 2 nicety. |
| Mono EQ in modal band | Bass is largely omnidirectional; one corrective EQ for the modal region (applied identically to L and R) is standard and avoids stereo-correction complexity. |
| Prefer cuts, **hard** boost ceiling | Boosting room nulls is futile and wastes headroom. Enforced as an *optimizer constraint* (default +2 dB), not a soft penalty that can leak small boosts. Clipping/preamp predictor runs before fit finalization. |
| Q floor permits narrow modes | Room modes < 100 Hz can be sharp (Q ~10–12); the room `FitObjective` must not inherit `peq.py`'s headphone bias toward broad low-Q filters, or it would smooth real modes away. |
| Room target flat in-band | We only EQ ≤ cutoff, so the in-band target is flat; the tilt house-curve is overlay-only. |
| CLI + offline first, GUI fast-follow | Keeps the experimental MVP small. Deliberately bends the GUI-first product rule for a beta feature; GUI is Phase 1.5. |
| Mic cal strongly required (not hard-blocked) | `doctor` check + loud confidence penalty if absent; proceeding without it is allowed but clearly marked low-trust. |

---

## 7. CLI surface

Two commands mirror the existing `measure`/`fit` split:
- **`room-measure`** plays the sweep live and records at the seat (online path).
- **`room-fit`** processes an already-captured recording (offline path).

```bash
# Online: play a sweep through the speaker and record at the listening seat
headmatch room-measure --mic-cal umik.csv [--cutoff-hz 300] [--max-boost-db 2] \
    [--out-dir ./room_fit]

# Online with the optional second seat position (energy-averaged)
headmatch room-measure --mic-cal umik.csv --listen-position-two [--out-dir ./room_fit]

# Offline: fit from a recording made with an external recorder
headmatch room-fit --recording room.wav --mic-cal umik.csv [--cutoff-hz 300] \
    [--recording-two room_pos2.wav] [--target-csv house_curve.csv] [--out-dir ./room_fit]

# Setup check
headmatch doctor    # adds: USB mic detected? mic-cal file readable + covers 20–500 Hz?
```

---

## 8. Output contract

Same folder pattern as existing fits, so users can open the folder and understand it:

- `README.txt` — plain-language explanation, **including the single-point and
  ≤-cutoff-only caveats**.
- `run_summary.json` — `workflow: "room"`, `cutoff_hz`, `mic_cal_applied: bool`,
  `single_point: true`, confidence fields.
- `room_fr.csv` — corrected, full-range in-room measurement.
- `equalizer_apo.txt` — **band-limited** parametric preset (no filters above cutoff).
- `camilladsp_filters_only.yaml` / `camilladsp_full.yaml` — band-limited.
  - **Q parameterization:** APO and CamillaDSP define Q/bandwidth differently; the export
    layer (reused `exporters.py`) must emit each platform's convention. The band-limit and
    boost-ceiling are applied to the fit *before* export, so both exporters receive the
    same constrained band set — this is verified by an export-parity test (§10).
- One SVG review graph: full-range measured FR + house-curve overlay + **shaded
  ≤cutoff EQ region** so the corrected vs measured-only split is visually obvious.
- Confidence / trust summary.

---

## 9. Confidence & trust

Reuse `pipeline_confidence.py`, adding room-specific caveats:

- **Single-position warning** — "Measured at one seat; a dip here may be a seat-specific
  null, not a room-wide problem. Multi-point averaging will improve this."
- **Sub-bass reliability** — flag results below ~20–30 Hz as low-confidence
  (room/mic/level limited).
- **Missing-calibration penalty** — significant confidence reduction + explicit warning
  when no mic-cal file was supplied.

---

## 10. Testing (TDD)

| Test | Asserts |
|---|---|
| `mic_cal` parse | UMIK-style CSV with header/comment/`Sens Factor` lines parses to correct `(freq, dB)` rows; comma-, whitespace-, and **tab**-separated all accepted; `Frequency(Hz),Magnitude(dB)` header tolerated |
| `mic_cal` scale guard | A file with ±50 dB values (a target/measurement CSV by mistake) is rejected/warned, not silently applied |
| `mic_cal` coverage guard | A cal file not spanning 20–500 Hz triggers a warning |
| `mic_cal` interp | PCHIP interpolation onto the FR grid; held-flat (not extrapolated) outside cal range |
| `mic_cal` apply | Offset is added to the measured magnitude correctly; relative-FR-only (sensitivity/SPL ignored) |
| **Band-limit invariant** | Fit places **zero** filters above `cutoff_hz` for any input |
| **Hard boost ceiling** | No fitted band exceeds `max_boost_db` for any input, including a deep-null input designed to tempt a large boost |
| **Q floor** | A synthetic +6 dB peak at 60 Hz with **Q=8** produces a corrective cut matching frequency **and Q** (within tolerance), not just depth — proves narrow modes aren't smoothed away |
| Flat room | A flat corrected FR yields a ~flat (near-empty) EQ |
| Sub-bass rolloff | Target tilts down ~2–3 dB below ~40 Hz; fit does not chase a huge sub-bass boost |
| Two-position average | Two recordings energy-average in the magnitude domain; a null present in only one position is attenuated, not aggressively corrected |
| Alignment latency tolerance | Cross-correlation alignment recovers the correct FR when round-trip latency varies by ±50 ms (simulated USB-mic latency); early IR energy not clipped |
| Export parity | APO and CamillaDSP exports are emitted from the same band-limited, boost-capped fit, each in its own Q convention |
| Missing cal | Confidence penalty applied + warning present in summary |
| Offline round-trip | `room-fit` writes all expected artifacts (CSV, APO, CamillaDSP, SVG, README, summary) |

Target: keep the new modules at the project's 100%-coverage bar for core modules.

---

## 11. Explicit YAGNI / Phase 2+

Named here so they are deferred, not silently dropped:

- **Full multi-point spatial averaging (MMM / N-position)** — the MVP ships an *optional
  two-position* average (§4.1); generalising to N positions and the moving-mic method is
  the highest-value next step beyond that.
- **RT60 / impulse-response diagnostics** → enables **adaptive Schroeder cutoff** and
  proper group-delay tracking.
- **Room-dimensions input** for a rough Schroeder estimate to validate/adjust the cutoff
  without RT60.
- **Full-range tilt EQ** above the modal region (with heavy smoothing + gain ceiling).
- **Per-speaker stereo correction** and sub/main crossover alignment.
- **GUI "Room (beta)" view** — Phase 1.5.

---

## 12. Resolved questions (from architectural review)

1. **Cutoff default — 300 Hz, configurable.** Kept at 300 Hz (safe-margin for typical
   small rooms), with a logged typical-room Schroeder estimate and a large-room caveat
   (§6). 250 Hz is a one-flag change for conservative users.
2. **Missing mic-cal — soft block.** CLI allows it with a confidence penalty + warning;
   `doctor` flags it. A GUI hard-block can be reconsidered when the GUI view lands
   (Phase 1.5) — not decided now.
3. **Example house-curve CSVs — ship two.** A flat-to-cutoff target plus one gently
   tilted in-room house curve, alongside the existing `docs/examples/targets/` curves,
   so the overlay is meaningful out of the box.

## 13. Review-driven additions (incorporated)

This spec was reviewed by `companion-architectural-review`
(`task_20260625133532_ff06dcca027fee69`). Verdict: architecturally sound, DSP strategy
correct, pipeline reuse justified. The following review findings are folded in above:

- Optional **two-position average** (§2, §4.1, §7) to mitigate the single-point null risk.
- **Hard boost ceiling** as an optimizer constraint + clipping check pre-finalization (§3.1, §6).
- **Q floor** so narrow sub-100 Hz modes aren't smoothed away (§3.1, §6, §10).
- **Mic-cal**: relative-FR-only, scale/coverage validation, tolerant parsing (§3.1, §10).
- **Sub-bass target rolloff** below ~40 Hz (§5).
- **USB-mic latency** alignment tolerance test (§3.3, §10).
- **Export Q-convention** parity between APO and CamillaDSP (§8, §10).
- Explicit notes: **speaker FR is not separated** (§5); **grid density** for narrow
  modes (§4.2); **mono = mono EQ output**, not mono capture (§2).
