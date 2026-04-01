# TASK-026 — Add Equalizer APO parametric preset export

## Summary
Export Equalizer APO-compatible parametric preset files by default for fit results.

## Context
Users need an APO-compatible preset file in addition to CamillaDSP output. The attached example uses Equalizer APO parametric filter syntax with `Preamp` and `Filter N: ON ...` lines.

## Scope
- Add Equalizer APO parametric preset export.
- Write it by default for fit outputs and iterative outputs.
- Keep the export compatible with the attached syntax style.
- Add tests for file generation and format correctness.

## Out of scope
- GraphicEQ export.
- Peace-specific extras beyond baseline APO compatibility.
- New GUI/TUI flows.

## Acceptance criteria
- Fit outputs include an APO-compatible preset text file.
- Iteration outputs include the same APO file.
- Export syntax is compatible with Equalizer APO parametric preset format.
- Tests cover the exporter and pipeline integration.

## Suggested files/components
- `headmatch/exporters.py`
- `headmatch/pipeline.py`
- `tests/`
