# HeadMatch backlog

## Current status

The current shipped state includes:
- beginner-first CLI workflow
- TUI wizard and history browsing
- GUI shell, history browsing, and measurement wizard
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

## Active

No immediate implementation tasks are open.

## Future follow-up candidates

1. Add GraphicEQ export if there is a clear user need beyond parametric APO presets.
2. Add export formats beyond CamillaDSP and APO if users actually need them.
3. Improve PipeWire device discovery and guidance further if users still struggle with manual target matching.
4. Add result interpretation and confidence scoring so users can tell whether a run is trustworthy.
5. Add a guided troubleshooting flow for common setup and measurement failures.
6. Add preset/run comparison workflows so users can compare stock, corrected, and clone-target results more easily.
7. Improve installation and release ergonomics, including launcher polish and environment diagnostics.
8. Add more published curve examples if clone-target workflows generate repeated support questions.
9. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
10. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
