# TASK-095: Feature – Clipping assessment

**Status**: ✅ Completed (2026-04-06)

**Summary**: Implement clipping prediction when assessing measurement quality.

## Context

When EQ filters have positive gain at some frequencies, applying them can push the signal above 0 dBFS, causing digital clipping. The standard mitigation is to apply a preamp (global negative gain) equal to the maximum positive boost, but this reduces signal-to-noise ratio.

## Implementation

### Completed work

1. **Created `headmatch/eq_clipping.py`** — New module with:
   - `EQClippingAssessment` dataclass for structured results
   - `assess_eq_clipping()` function to evaluate PEQ bands
   - `format_clipping_assessment()` for human-readable output
   - `format_clipping_summary()` for concise logging
   - Quality concern warnings for moderate (>6 dB) and severe (>12 dB) headroom loss

2. **Integrated into `headmatch/pipeline.py`**:
   - Clipping assessment runs automatically in `fit_from_measurement()`
   - Results stored in `report['eq_clipping']` dict:
     - `will_clip` (bool)
     - `left_peak_boost_db` / `right_peak_boost_db` (float)
     - `preamp_db` (float, the required preamp gain to prevent clipping)
     - `headroom_loss_db` (float)
     - `quality_concern` (str | None)

3. **Added comprehensive tests** (`tests/test_eq_clipping.py`):
   - 13 test cases covering:
     - No bands (no clipping)
     - Positive boost (clipping detected)
     - Negative boost only (no clipping)
     - Mixed boosts and cuts
     - Different left/right channels
     - Headroom loss warnings (moderate and severe)
     - Formatting functions
     - Integration with actual PEQ fitting

### How it works

1. After fitting PEQ bands, compute the EQ response curve using `peq_chain_response_db()`
2. Find the maximum positive boost in the curve
3. The required preamp is the negative of the peak boost
4. If headroom loss exceeds thresholds, generate quality concern messages

### Example output

```
EQ Clipping Assessment:
  ⚠️  Positive boost detected — preamp required to prevent clipping.
  Left peak boost:  +6.0 dB
  Right peak boost: +6.0 dB
  Preamp needed:     -6.0 dB
  Note: Moderate headroom loss (6.0 dB). EQ pushes may reduce signal-to-noise ratio when compensated with preamp.
```

## Scope

- ✅ Add logic to predict EQ clipping after fitting
- ✅ Expose metrics in the fit report (`eq_clipping` dict)
- ✅ Compute required preamp gain
- ✅ Generate quality concern messages for severe cases
- ✅ Unit tests cover all clipping scenarios

## Out‑of‑Scope

- Recording audio clipping detection (separate concern)
- Automatic preamp application in export — not addressed
- Advanced multi‑band clipping analysis — not addressed

## Acceptance Criteria

- ✅ Clipping prediction runs after PEQ fit
- ✅ Preamp gain computed and stored in report
- ✅ Quality concerns generated for severe headroom loss
- ✅ Unit tests cover clipping detection cases

## Test Summary

- 520 tests pass (507 original + 13 new)
- All integration tests with PEQ fitting pass
