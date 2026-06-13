# TASK-116 — Hearing measurement & personalised EQ compensation

## Summary

Add a self-administered pure-tone hearing measurement workflow that
sweeps a set of test frequencies, estimates the user's hearing thresholds
via the Modified Hughson-Westlake procedure (Carhart & Jerger 1959,
public domain), and converts the result to an EQ compensation curve
using the half-gain rule (Lybarger 1944, public domain).  The
compensation curve is folded into the target before the existing PEQ
fitter runs — so the final preset corrects both the headphone's acoustic
response and the user's hearing profile simultaneously.

---

## Background & methodology

All procedures reference published, public-domain audiological science.
No proprietary algorithm or patented DSP method is used.

### Frequency set

Seven test bands in decade-logarithmic spacing, covering the
perceptually important 500 Hz – 8 kHz range where age- and noise-related
threshold shifts are most pronounced (ISO 8253-1 §5.2):

```
500 Hz, 1 000 Hz, 2 000 Hz, 3 000 Hz, 4 000 Hz, 6 000 Hz, 8 000 Hz
```

Testing order follows ISO 8253-1: start at 1 000 Hz (most reliable
reference), ascend to 2 000 → 3 000 → 4 000 → 6 000 → 8 000 Hz,
re-verify 1 000 Hz (must agree ± 5 dB), then descend to 500 Hz.  This
order minimises adaptation effects.

### Threshold detection — Modified Hughson-Westlake ("up-5 down-10")

Classic procedure from Carhart & Jerger (1959), still the ISO 8253-1
reference method.  For each frequency:

1. Present a familiarisation tone at `start_level_dB` (see below) — a
   level comfortably above threshold.
2. After each *heard* response: decrease level 10 dB.
3. After each *not-heard* silence: increase level 5 dB.
4. An **ascending run** is completed when the user responds after one or
   more silent (not-heard) presentations.
5. **Threshold** = lowest level that produced a response on ≥ 2 of the
   last 3 ascending runs.
6. Minimum 3 ascending runs required before declaring threshold.
7. Maximum 8 ascending runs; if no stable threshold after 8 runs, the
   frequency is marked as `UNDETERMINED` and skipped in compensation.

### Starting level

Because HeadMatch has no RETSPL calibration table (device-specific
dB HL conversion offsets), the test operates in **relative dB units**:
level 0 = nominal digital silence, level 100 = full-scale headphone
output.  An empirically reasonable starting point is level **60** (≈
comfortable listening for normal hearing at most headphone models at
typical playback volumes).  The user is told to set their system volume
to a comfortable music-listening level before starting; the test is
calibrated against that anchor.

### Ambient noise gate

Record 1.5 s of silence via the active `AudioBackend` before the first
tone.  Compute RMS of the captured buffer.  If the ambient noise floor
exceeds `NOISE_GATE_THRESHOLD` (default: –30 dBFS), display a warning
and allow the user to retry.  Do not abort silently.

### Tone stimulus

- Pure sine wave, duration **1 000 ms**
- 30 ms raised-cosine (Hann) onset and offset ramps (eliminates
  spectral splatter and audible clicks)
- 800 ms inter-stimulus interval of silence between tones
- No pulsed pattern (single continuous burst keeps UI response mapping
  simple)

### Compensation curve — half-gain rule (Lybarger 1944)

For each tested frequency `f`:

```
ref_level(f)    = median level across all users who responded at f
                  (seeded from a built-in normal-hearing baseline table;
                   see hearing_test.py NORMAL_HEARING_REFERENCE)
loss(f)         = measured_threshold(f) - ref_level(f)
gain(f)         = max(0, loss(f)) * GAIN_FRACTION
                  where GAIN_FRACTION = 0.50  (half-gain rule)
gain(f)         = clamp(gain(f), 0.0, MAX_COMPENSATION_DB)
                  where MAX_COMPENSATION_DB = 12.0
```

The resulting 7-point `(log_freq, gain_dB)` curve is interpolated to
the existing HeadMatch frequency grid using **cubic spline interpolation
on a log-frequency axis** (scipy.interpolate.CubicSpline), then
smoothed with a 1-octave Gaussian kernel to prevent sharp filter
transitions.

The compensation curve is then **added to the active target curve**
before the PEQ fitter runs:

```
effective_target(f) = base_target(f) + hearing_compensation(f)
```

This reuses the entire existing pipeline unchanged.  The fitter sees a
target that already encodes both the desired headphone response and the
hearing profile correction.

### Per-ear measurement

Both ears are tested independently.  L/R compensation curves are
averaged before being applied to the mono target (headphone measurements
in HeadMatch are per-channel but the target curve is mono).  If the
L/R asymmetry at any frequency exceeds 15 dB, a warning is shown
("consider consulting an audiologist") but processing continues.

---

## New modules

### `headmatch/hearing_test.py`

Core test engine.  No GUI or I/O dependencies.

```
NORMAL_HEARING_REFERENCE: dict[int, float]
    Built-in baseline table (freq_hz → relative_level).
    Derived from ISO 7029:2017 median thresholds for 18-year-olds,
    mapped to HeadMatch's relative dB scale.

TEST_FREQUENCIES: tuple[int, ...]   = (500, 1000, 2000, 3000, 4000, 6000, 8000)
TEST_ORDER: tuple[int, ...]         = (1000, 2000, 3000, 4000, 6000, 8000, 1000, 500)
MAX_ASCENDING_RUNS: int             = 8
THRESHOLD_RESPONSES_NEEDED: int     = 2
THRESHOLD_WINDOW: int               = 3
GAIN_FRACTION: float                = 0.50
MAX_COMPENSATION_DB: float          = 12.0
NOISE_GATE_THRESHOLD_DBFS: float    = -30.0

@dataclass
class FrequencyThreshold:
    freq_hz: int
    level: float          # relative dB; None if UNDETERMINED
    ascending_runs: int
    determined: bool

@dataclass
class HearingProfile:
    left: dict[int, FrequencyThreshold]
    right: dict[int, FrequencyThreshold]
    tested_at: str        # ISO 8601 timestamp
    asymmetric_freqs: list[int]   # freqs where L/R gap > 15 dB

class ThresholdEngine:
    """State machine for a single-ear, single-frequency threshold search."""
    def __init__(self, start_level: float, freq_hz: int) -> None: ...
    def next_level(self) -> float: ...
    def record_response(self, heard: bool) -> None: ...
    @property
    def threshold(self) -> float | None: ...
    @property
    def done(self) -> bool: ...

def generate_tone(freq_hz: int, level_db: float,
                  sample_rate: int = 48000) -> np.ndarray:
    """Pure sine with 30 ms Hann ramps at normalised level."""

def measure_noise_floor(backend: AudioBackend,
                        device_config: DeviceConfig,
                        duration_s: float = 1.5) -> float:
    """Returns RMS in dBFS from a short silence recording."""

def compute_compensation_curve(
    profile: HearingProfile,
    freq_grid: np.ndarray,          # HeadMatch log frequency grid
) -> np.ndarray:
    """
    Returns gain_db per freq_grid point.
    Averages L/R thresholds, applies half-gain rule, cubic-spline
    interpolates, then 1-octave Gaussian smooth.
    """

def save_hearing_profile(profile: HearingProfile, paths: AppPaths) -> Path:
    """Writes ~/.config/headmatch/hearing_profile.json."""

def load_hearing_profile(paths: AppPaths) -> HearingProfile | None:
    """Returns None if no saved profile exists."""
```

### `headmatch/pipeline.py` (modification)

Add optional parameter to `run_pipeline()`:

```python
hearing_profile: HearingProfile | None = None
```

When present, `compute_compensation_curve()` is called and the result
added to the target array before PEQ fitting.  No other pipeline logic
changes.

### `headmatch/contracts.py` (modification)

Add `WorkflowName` literal: `"hearing_test"`.

Add dataclass:

```python
@dataclass
class HearingTestResult:
    profile: HearingProfile
    compensation_curve_path: Path   # saved SVG preview
    applied_to_run: str | None      # run_id if immediately applied
```

### `headmatch/gui/views/hearing_test.py`

New GUI view module.  Follows the existing view pattern (returns a
rendered Tkinter frame; all state flows through callbacks to the
controller).

States (rendered as distinct sub-frames within the view):

```
INTRO        → NOISE_CHECK  → TESTING_EAR_L  → TESTING_EAR_R
           → RESULTS → APPLY_CONFIRM
```

Key UI elements per state:

**INTRO**
- Brief plain-language explanation of the test
- "Make sure you're in a quiet room and set volume to a comfortable
  music level"
- `[Start Test]` button

**NOISE_CHECK**
- Progress spinner while ambient noise is sampled
- Pass: transitions automatically to TESTING_EAR_L
- Fail: red warning + `[Retry]` + `[Skip check and continue]`

**TESTING_EAR_L / TESTING_EAR_R**
- Header: "Testing left ear — cover your right ear" (or vice versa)
- Frequency progress: `"Frequency 3 / 7 — 2 000 Hz"`
- Large `[I hear it]` button (primary action)
- Tone is played automatically on entry to each level step; a small
  animated speaker icon shows when the tone is active
- No "I don't hear it" button — silence = no response (simpler UX,
  avoids false negatives from slow button press)
- Response window: 3 000 ms from tone onset; if no tap within window,
  records "not heard" and plays next step
- `[Stop test]` link in corner (discards result)

**RESULTS**
- Simple bar chart (canvas-drawn, matches existing SVG style) showing
  estimated threshold by frequency for each ear
- Asymmetry warnings shown inline if L/R differ > 15 dB
- `[Apply to next EQ run]` button (saves profile + sets
  `pending_hearing_compensation = True` in GUI state)
- `[Save without applying]` button
- `[Discard]` link

**APPLY_CONFIRM**
- One-line summary: "Your hearing compensation (+X dB average) will be
  added to the target curve in the next measurement run."
- `[OK]` → returns to main shell

### `headmatch/gui/controllers.py` (modification)

Add `HearingTestController`:

```python
class HearingTestController:
    def __init__(self, backend: AudioBackend, paths: AppPaths,
                 on_complete: Callable[[HearingTestResult], None]) -> None: ...

    def start(self, device_config: DeviceConfig) -> None:
        # 1. noise floor check
        # 2. iterate through TEST_ORDER for left ear
        #    - play tone via backend (direct output, no recording)
        #    - wait for GUI response or timeout
        #    - feed to ThresholdEngine
        # 3. repeat for right ear
        # 4. compute profile, save, call on_complete

    def _play_tone(self, freq_hz: int, level_db: float) -> None:
        # Generates tone buffer via generate_tone()
        # Plays via backend.play() (new thin play-only method; see below)
```

### `headmatch/audio_backend.py` (modification)

Add `play_tone()` to the `AudioBackend` protocol:

```python
def play_tone(self, samples: np.ndarray, sample_rate: int,
              device: str | None = None) -> None:
    """Play a short buffer to the output device without recording."""
```

Implement in both `PipeWireBackend` (write samples to a temp WAV, call
`pw-play`) and `PortAudioBackend` (call `sd.play(samples, sample_rate,
blocking=True)`).

---

## CLI surface

```
headmatch hearing-test
    Run the hearing test (TUI / headless mode, left ear then right ear).
    Plays tone, waits for Enter key = heard, silence timeout = not heard.
    Saves profile to config dir.
    --device <name|id>          output device override
    --no-noise-check            skip ambient noise gate
    --json                      emit HearingTestResult JSON to stdout

headmatch fit --with-hearing-compensation
    Load saved hearing profile and fold into target before fitting.
    Errors with clear message if no saved profile found.
```

---

## Persistence

Profile saved as human-readable JSON at:
- Linux: `~/.config/headmatch/hearing_profile.json`
- macOS: `~/Library/Application Support/headmatch/hearing_profile.json`
- Windows: `%APPDATA%/headmatch/hearing_profile.json`

Schema (matches `HearingProfile` dataclass, serialised via `dataclasses.asdict`):

```json
{
  "tested_at": "2026-06-13T22:00:00Z",
  "asymmetric_freqs": [],
  "left": {
    "500":  { "freq_hz": 500,  "level": 58.0, "ascending_runs": 3, "determined": true },
    "1000": { "freq_hz": 1000, "level": 60.0, "ascending_runs": 3, "determined": true },
    ...
  },
  "right": { ... }
}
```

---

## Integration points with existing pipeline

```
gui/shell.py
  └─ HearingTestController
       └─ ThresholdEngine × 14 (7 freq × 2 ears)
       └─ AudioBackend.play_tone()
       └─ save_hearing_profile()
  └─ HearingTestView (gui/views/hearing_test.py)

pipeline.py  run_pipeline(hearing_profile=...)
  └─ compute_compensation_curve(profile, freq_grid)  → gain array
  └─ effective_target = base_target + compensation
  └─ [existing peq.py fit — unchanged]
  └─ [existing exporters.py — unchanged]

run_summary.json (no schema change)
  hearing_compensation_applied: bool   ← new field, optional
```

---

## Design decisions & constraints

| Decision | Rationale |
|---|---|
| Relative dB scale, not dB HL | No RETSPL calibration data per headphone model; avoids false clinical claims |
| Half-gain rule (0.5×) | Public domain (Lybarger 1944); conservative; appropriate for music listening, not speech intelligibility |
| Cap at +12 dB | Prevents runaway boost on frequencies where driver distortion is high |
| Fold into target, not separate EQ layer | Reuses existing pipeline; single artefact per run; no architectural new EQ stage |
| Per-ear then averaged to mono | Matches existing mono-target pipeline; asymmetry warning surfaced but not fatal |
| 7 test frequencies | Balances resolution (better than 4-point PTA minimum) with test time (~4 min total) |
| No "I don't hear it" button | Reduces false positives from hesitation; silent timeout is the standard response |
| 3 s response window | Longer than clinical (1 s) to accommodate consumer UX latency |
| Built-in normal-hearing reference | Enables compensation without needing a prior calibration run |

---

## Acceptance criteria

- [ ] Tone playback works on PipeWire (Linux) and PortAudio (macOS/Windows) via the existing backend
- [ ] ThresholdEngine produces stable threshold within 3–8 ascending runs for a simulated perfect listener
- [ ] Compensation curve: 0 dB at all frequencies for a "flat" (at-reference) hearing profile
- [ ] Compensation curve: +10 dB at 4 kHz for a profile with 20 dB of loss at 4 kHz (half-gain = 10)
- [ ] `pipeline.py` with `hearing_profile` produces a different (boosted) effective target than without
- [ ] GUI flow completes end-to-end without crashing on Linux desktop
- [ ] Saved profile round-trips through JSON serialisation
- [ ] `headmatch hearing-test --json` emits valid JSON
- [ ] `headmatch fit --with-hearing-compensation` loads saved profile and runs
- [ ] L/R asymmetry warning shown correctly when gap > 15 dB
- [ ] Noise gate warning shown and non-blocking

---

## Suggested files / components

**New files:**
- `headmatch/hearing_test.py`
- `headmatch/gui/views/hearing_test.py`
- `tests/test_hearing_test.py`
- `tests/test_hearing_compensation.py`

**Modified files:**
- `headmatch/audio_backend.py` — add `play_tone()` to protocol
- `headmatch/backend_pipewire.py` — implement `play_tone()`
- `headmatch/backend_portaudio.py` — implement `play_tone()`
- `headmatch/contracts.py` — add `WorkflowName` literal + `HearingTestResult`
- `headmatch/pipeline.py` — add `hearing_profile` parameter
- `headmatch/gui/controllers.py` — add `HearingTestController`
- `headmatch/gui/shell.py` — wire new view + controller, add hearing test entry point
- `headmatch/cli.py` — add `hearing-test` and `fit --with-hearing-compensation`

---

## Out of scope for this task

- Dynamic compression / WDRC (requires per-band compressor in the DSP chain; separate task)
- RETSPL calibration per headphone model (requires a calibration database; separate task)
- Bone-conduction testing
- Speech-in-noise testing
- Clinical audiogram import (can be added later by mapping dB HL → relative dB via a stored RETSPL table)
- Extended high-frequency testing above 8 kHz
