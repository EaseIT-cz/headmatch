# TASK-077 — Research and fix dense GraphicEQ clipping

## Summary
The dense GraphicEQ export (equalizer_apo_graphiceq.txt) still clips in real-world use despite the 0.4.4 fix that changed it from raw target to PEQ-fitted response. The feature should be considered broken until this is resolved.

## Context
A user reported clipping when loading the dense GraphicEQ preset from a clone-target run (HD650 → Focal Clear MG, 5-pass average, 31 max filters). The parametric APO preset from the same run works fine.

The 0.4.4 fix changed the dense export from writing the raw correction target to writing the PEQ-fitted response. This should have fixed it, but the user reports it still clips. Possible causes:

1. The PEQ-fitted response at 48 PPO resolution reproduces narrow peaks/troughs between the placed PEQ bands that sum to excessive gain at certain frequencies.
2. The preamp calculation may be incorrect — it takes the max of the gain array, but the GraphicEQ interaction between adjacent bands could produce cumulative gain above any single band's value.
3. Equalizer APO's GraphicEQ interpolation between the dense points may overshoot.
4. The per-channel preamp may need more headroom margin (e.g., -1 dB safety margin).

## Research needed
- Reproduce with the user's data (measurement CSVs and target attached to the bug report).
- Compare the dense GraphicEQ gains against the parametric preset's actual frequency response.
- Check if the preamp provides sufficient headroom for the cumulative GraphicEQ response.
- Test whether adding a safety margin (e.g., 1-2 dB extra preamp cut) resolves the clipping.
- Consider whether the dense GraphicEQ format is fundamentally the right approach, or whether a fixed-band GraphicEQ (10 or 31 band) would be more appropriate as the default non-parametric export.

## Acceptance criteria
- Dense GraphicEQ export does not clip in Equalizer APO for typical headphone measurements.
- Or: the dense export is replaced with a fixed-band GraphicEQ that is known to be safe.
- Preamp headroom is documented and tested.

## Suggested files
- `headmatch/pipeline.py` (export call site)
- `headmatch/exporters.py` (preamp calculation, GraphicEQ formatting)
- `tests/test_integration_cli.py` (regression test)
