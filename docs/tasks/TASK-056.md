# TASK-056 — Add Equalizer APO GraphicEQ export

## Summary
Add a GraphicEQ-format Equalizer APO export alongside the existing parametric APO preset.

## Context
HeadMatch already exports parametric Equalizer APO presets. The next useful step is a GraphicEQ-format export for Equalizer APO/Peace users who prefer or require a graphic-EQ style representation.

This should be implemented as an additional export on top of the shared target/objective layer, not as a replacement for PEQ and not yet as a full fixed-band fitting mode.

## Scope
- Add a GraphicEQ-format Equalizer APO export file.
- Base it on the shared effective target/correction layer so it reflects the intended correction, not an unrelated ad hoc transform.
- Keep the existing parametric APO export intact.
- Update generated guides/docs/tests as needed.

## Out of scope
- Replacing PEQ export.
- Full fixed-band GraphicEQ fitting mode.
- GUI redesign.

## Acceptance criteria
- Fit outputs include a usable GraphicEQ-format Equalizer APO export.
- Existing parametric APO export remains available.
- Output guides/docs mention the new file clearly.
- Full test suite passes.

## Suggested files/components
- `headmatch/exporters.py`
- `headmatch/pipeline.py`
- `README.md`
- `tests/test_peq_exporters.py`
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py`
