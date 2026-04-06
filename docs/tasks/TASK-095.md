# TASK-095: Feature – EQ clipping assessment

**Status**: ✅ Completed (2026-04-06)

**Summary**: Forecast whether the generated EQ profile will cause clipping when applied, and include this prediction in the quality assessment after fitting completes.

## Problem Statement

When EQ filters have positive gain at some frequencies, applying them can push the signal above 0 dBFS, causing digital clipping. Users need to know:

1. **Will the EQ clip?** — Predictive assessment before applying
2. **How much preamp is needed?** — Mitigation strategy
3. **Is the preamp loss acceptable?** — Quality impact assessment

## Implementation

### Core module: `headmatch/eq_clipping.py`

```python
@dataclass
class EQClippingAssessment:
    will_clip: bool              # True if any positive boost exists
    left_peak_boost_db: float    # Max positive boost (dB)
    right_peak_boost_db: float   # Max positive boost (dB)
    preamp_db: float             # Required preamp (negative, dB)
    headroom_loss_db: float      # SNR loss from preamp
    quality_concern: str | None  # Warning if severe

def assess_eq_clipping(freqs, sr, left_bands, right_bands) -> EQClippingAssessment:
    # Compute EQ response curve
    # Find max positive boost
    # Calculate preamp = -peak_boost
    # Generate quality concerns for severe loss
```

### Integration: `headmatch/pipeline.py`

The clipping assessment runs automatically in `fit_from_measurement()`:

```python
# After fitting PEQ bands:
clipping_assessment = assess_eq_clipping(result.freqs_hz, sample_rate, left_bands, right_bands)
report['eq_clipping'] = {
    'will_clip': clipping_assessment.will_clip,
    'left_peak_boost_db': clipping_assessment.left_peak_boost_db,
    'right_peak_boost_db': clipping_assessment.right_peak_boost_db,
    'preamp_db': clipping_assessment.total_preamp_db,
    'headroom_loss_db': clipping_assessment.headroom_loss_db,
    'quality_concern': clipping_assessment.quality_concern,
}
```

### How it works

1. **Compute EQ response** — Uses existing `peq_chain_response_db()` to get the full EQ curve
2. **Find peak positive boost** — The maximum value in the EQ curve
3. **Calculate preamp** — Preamp = -peak_boost (negative gain to prevent clipping)
4. **Assess quality impact** — If headroom loss > 6 dB → moderate warning, > 12 dB → severe warning

### Example output

For an EQ with +8 dB boost at 2 kHz:
```
will_clip: True
left_peak_boost_db: 8.0
right_peak_boost_db: 8.0
preamp_db: -8.0
headroom_loss_db: 8.0
quality_concern: "Moderate headroom loss (8.0 dB). EQ pushes may reduce signal-to-noise ratio..."
```

## Acceptance Criteria

- ✅ Clipping prediction runs after PEQ fit
- ✅ Forecast whether EQ will clip when applied
- ✅ Preamp gain computed and included in report
- ✅ Quality concerns generated for severe headroom loss
- ✅ Unit tests cover all clipping scenarios (13 tests)

## Test Summary

- 520 tests pass (507 original + 13 new EQ clipping tests)
- Tests cover: empty EQ, positive boost, negative boost, mixed, asymmetric L/R, quality warnings, formatting, integration with fitting

## Files Changed

- `headmatch/eq_clipping.py` — New module (151 lines)
- `headmatch/pipeline.py` — Integration in fit_from_measurement()
- `tests/test_eq_clipping.py` — 13 comprehensive tests
- `docs/tasks/TASK-095.md` — This task document
- `docs/backlog.md` — Updated status

## Out of Scope

- Automatic preamp application in APO/CamillaDSP export
- Recording audio clipping detection (separate concern)
- Multi-band clipping analysis (per-octave assessment)
