# TASK-057 — Add fixed-band GraphicEQ fitting

## Summary
Add a true fixed-band GraphicEQ fitting mode so HeadMatch can optimize directly for graphic-EQ style outputs instead of only exporting a dense GraphicEQ approximation from the shared correction curve.

## Context
HeadMatch now supports:
- conservative up-to-N PEQ
- exact-count PEQ
- additive Equalizer APO GraphicEQ export

The next logical step is to fit directly onto a fixed GraphicEQ band model so device-constrained workflows can target the actuator they will actually use.

## Scope
- Add a fixed-band GraphicEQ fitting mode in the backend.
- Build it on top of the shared objective/residual layer.
- Preserve existing PEQ modes and existing dense GraphicEQ export.
- Add tests for fixed-band fitting behavior and export/output plumbing as needed.

## Out of scope
- Broad GUI redesign.
- Replacing PEQ modes.
- Device-specific presets beyond a sensible default fixed-band profile.

## Acceptance criteria
- Backend can produce a fixed-band GraphicEQ result directly from the fit objective.
- Existing PEQ and current GraphicEQ export paths remain available.
- The design stays compatible with future additional fixed-band profiles if needed.
- Full test suite passes.

## Suggested files/components
- `headmatch/peq.py` or a sibling fitting module
- `headmatch/exporters.py`
- `headmatch/pipeline.py`
- `tests/test_peq_exporters.py`
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py`
