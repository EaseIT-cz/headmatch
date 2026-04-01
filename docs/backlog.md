# HeadMatch backlog

## Current status

The current shipped state includes:
- beginner-first CLI workflow
- GUI shell, history browsing, and measurement wizard
- TUI backup workflow and history browsing (maintenance-only)
- shared settings persistence and preload
- improved capture/import robustness
- stronger alignment robustness coverage
- conservative PEQ/export polish
- clone examples and cross-source validation
- deterministic end-to-end synthetic integration tests
- GitHub Actions coverage for both main and integration test suites
- PipeWire device guidance
- measured-vs-target graph rendering
- Equalizer APO-compatible parametric preset export by default
- confidence / trust summaries in fit outputs

## Active

1. Surface confidence and interpretation more clearly in the GUI and CLI.

## Future follow-up candidates

1. Add a guided troubleshooting flow for common setup and measurement failures.
2. Improve PipeWire device discovery and guidance further if users still struggle with manual target matching.
3. Add GraphicEQ export if there is a clear user need beyond parametric APO presets.
4. Add export formats beyond CamillaDSP and APO if users actually need them.
5. Add preset/run comparison workflows so users can compare stock, corrected, and clone-target results more easily.
6. Improve installation and release ergonomics, including launcher polish and environment diagnostics.
7. Add more published curve examples if clone-target workflows generate repeated support questions.
8. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
9. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
10. Keep the TUI functional, but treat it as maintenance-only unless a clear use case reappears.
