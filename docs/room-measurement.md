# Room measurement workflow

This page documents the HeadMatch **room measurement workflow** (beta). It produces a **bass-only corrective EQ** for speakers in a room, using a calibrated USB microphone placed at the listening position.

> **Status:** Proposed / planned — not yet implemented. Design spec: `docs/designs/room-measurement.md`. Implementation plan: `docs/tasks/TASK-117.md`.

---

## Overview

HeadMatch can measure the acoustic response of your room and generate a corrective EQ for the **modal bass region** (typically ≤ 300 Hz). Above this cutoff, the response is measured and graphed, but no EQ is applied — minimum-phase parametric EQs cannot effectively correct reflections or comb-filtering problems.

This is an intentionally conservative approach: measure everything, correct only what works.

---

## Requirements

### Hardware

- **Speakers** — any stereo speaker system you want to measure
- **USB measurement microphone** — a calibrated USB mic (e.g. miniDSP UMIK-1/2) is **strongly recommended**
- **Computer** running Linux with PipeWire, or an external recorder for offline processing

### Microphone calibration file

You need a calibration file for your measurement microphone. These are typically provided by the mic manufacturer:

- Download from the manufacturer's website (e.g. miniDSP UMIK calibration downloads)
- Format: CSV or TXT with `frequency_hz, gain_db` data (tab, comma, or space separated)
- Must span at least **20 Hz – 500 Hz** (HeadMatch will warn if coverage is insufficient)

> **Important:** The calibration file provides **relative frequency response only**, not absolute SPL. HeadMatch uses the per-frequency deviation from flat, ignoring any absolute sensitivity calibration line (e.g. `Sens Factor = -38.4 dB` in UMIK files). You do not need a calibrator or SPL meter.

---

## Workflow

### Online (PipeWire)

Measure and fit in one session:

```bash
# Check setup
headmatch doctor

# Measure and fit
headmatch room-measure \
  --mic-cal umik_calibration.txt \
  --out-dir ./room_fit

# With optional second seat position (energy-averaged)
headmatch room-measure \
  --mic-cal umik_calibration.txt \
  --listen-position-two \
  --out-dir ./room_fit
```

### Offline (external recorder)

Prepare a sweep package, record with your recorder, then fit:

```bash
# Prepare sweep
headmatch prepare-offline --out-dir ./room_sweep

# ...record the sweep in your room, save as room_recording.wav...

# Process the recording
headmatch room-fit \
  --recording ./room_recording.wav \
  --mic-cal umik_calibration.txt \
  --out-dir ./room_fit

# Optional: include a second position
headmatch room-fit \
  --recording ./room_recording.wav \
  --recording-two ./room_recording_pos2.wav \
  --mic-cal umik_calibration.txt \
  --out-dir ./room_fit
```

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mic-cal PATH` | *required* | Path to microphone calibration file |
| `--cutoff-hz FLOAT` | 300.0 | Maximum frequency for EQ placement (Hz). Corrected below this, measured only above. |
| `--max-boost-db FLOAT` | 2.0 | Hard ceiling on boost values. Boosting room nulls is almost always wrong — this is enforced as a constraint, not just a penalty. |
| `--listen-position-two` | *disabled* | Capture an optional second listening position; measurements are energy-averaged before fitting. |
| `--target-csv PATH` | built-in flat | Custom target curve (see example targets below). |
| `--out-dir DIR` | *required* | Output directory for results. |

### Why `--cutoff-hz` matters

In a typical domestic room, the Schroeder frequency (boundary between modal and statistical acoustics) falls around 100–250 Hz. The default 300 Hz is a safe high-margin default for small-to-medium rooms. For larger/live rooms (volume > 150 m³, RT60 > 0.8 s), the modal region may extend lower; reduce the cutoff accordingly.

> The MVP does not measure RT60, so the cutoff is fixed, not adaptive. Phase 2 will add RT60-based adaptive cutoff.

### Why `--max-boost-db` matters

Room nulls are **position-dependent** and **cannot be effectively corrected** with minimum-phase EQ. Bass traps and/or subwoofer positioning are the correct solutions. The boost ceiling prevents the fitter from wasting headroom trying to boost uncorrectable nulls.

---

## Example room targets

Two example target curves are included in `docs/examples/targets/` for the room workflow:

### `room_flat.csv`

A flat response through the modal band with a gentle sub-bass rolloff below ~40 Hz. The rolloff prevents chasing unrealistic gain in the very low frequencies where room/mic/speaker limitations dominate.

### `room_house_curve.csv`

A gentle **bass lift** (house curve): elevated in the deep bass, returning to 0 dB by ~200 Hz. Pass it with `--target-csv` to fit toward it, or graph it over the measured response as an in-room reference. It expresses *how much to lift the bass relative to the through-band*, so it hands off cleanly at the cutoff instead of imposing a level change there.

Unlike headphone targets, room targets are **not** normalized at 1 kHz (they are naturally bass-only). Instead, `room-fit` anchors whatever target you pass to 0 dB at the cutoff, so only the target's *shape relative to the through-band* matters — its absolute level in the CSV is irrelevant. Targets follow the standard CSV format (`frequency_hz, target_db`); a bass-only curve (e.g. 20–300 Hz) is fine.

---

## Output files

A room fit produces the same artifact structure as headphone fits:

| File | Description |
|------|-------------|
| `README.txt` | Plain-language explanation, including caveats |
| `run_summary.json` | Machine-readable summary with `workflow: "room"`, cutoff, calibration status |
| `room_fr.csv` | Corrected, full-range in-room frequency response |
| `equalizer_apo.txt` | Parametric EQ preset (**band-limited**: no filters above cutoff) |
| `camilladsp_full.yaml` / `camilladsp_filters_only.yaml` | CamillaDSP configs (band-limited) |
| `room_overview.svg` | Review graph showing measured FR, target overlay, shaded EQ region |

---

## Important caveats and limitations (MVP)

### Single-point vs two-position

By default, the measurement is taken at **one seat position only**. Deep nulls at a specific position may be **position-specific**, not room-wide problems. The optional `--listen-position-two` flag enables a second position that is energy-averaged with the first, catching the worst nulls. Full multi-point spatial averaging (moving microphone method) is **Phase 2**.

### Bass-only correction scope

The fitter **only places EQ bands at or below the cutoff** (default: ≤ 300 Hz). Reflections, comb-filtering, and speaker resonances above this are measured and graphed so you can see them, but **not corrected**. A minimum-phase parametric EQ cannot meaningfully fix these issues. Manual EQ of measured peaks above the cutoff is at your own risk.

### Speaker FR is not separated

The measured response is **speaker + room combined**. HeadMatch does not deconvolve a manufacturer's anechoic speaker response from the room measurement. The correction targets the in-room response as a system.

### Sub-bass reliability

Results below ~20–30 Hz should be treated as **low confidence**: room limitations, mic noise floor, and speaker excursion limits dominate. The sub-bass rolloff in example targets acknowledges this.

### No RT60 / impulse diagnostics

The MVP is **frequency-response only**. There is no RT60 measurement, no group-delay analysis, and no adaptive Schroeder frequency calculation. Phase 2 will add these when impulse-response processing is available.

### Mono EQ output

The correction is **mono** (one EQ applied identically to both speaker channels). Bass is largely omnidirectional, and bass nulls tend to be similar for both channels at the listening position. Per-speaker stereo correction is **Phase 2**.

---

## Phase 2 future work

The room measurement MVP is intentionally conservative. Known deferred features:

- **Multi-point spatial averaging (MMM)** — moving microphone method for proper spatial averaging
- **RT60 measurement** — impulse-response based RT60 for adaptive Schroeder cutoff
- **Room dimensions input** — rough Schroeder estimate from dimensions without RT60
- **Group delay analysis** — separate minimum-phase and excess group delay
- **GUI room view** — integrated room measurement in the HeadMatch GUI
- **Full-range tilt EQ** — optional smoothed correction above cutoff (careful limits)
- **Per-speaker stereo correction** — separate L/R EQ for the modal region

See `docs/designs/room-measurement.md` and `docs/tasks/TASK-117.md` for design details and implementation status.

---

## Quick reference: typical command

```bash
headmatch room-measure \
  --mic-cal ~/Downloads/UMIK-1/calibration.txt \
  --cutoff-hz 300 \
  --max-boost-db 2.0 \
  --out-dir ./my_room_eq
```

This will measure your room, apply the microphone calibration, fit a **bass-only EQ** up to 300 Hz with no more than +2 dB boost, and export ready-to-load presets for Equalizer APO and CamillaDSP.