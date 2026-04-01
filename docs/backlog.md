# HeadMatch backlog

## Current status

There are no immediate implementation tasks open.

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
- measured-vs-target SVG review graphs in fit and iteration result folders

## Active

1. Improve PipeWire device discovery and guidance so users can more easily choose playback and capture targets.

## Future follow-up candidates

3. Add export formats beyond CamillaDSP if users actually need them.
4. Add result interpretation and confidence scoring so users can tell whether a run is trustworthy.
5. Add a guided troubleshooting flow for common setup and measurement failures.
6. Add preset/run comparison workflows so users can compare stock, corrected, and clone-target results more easily.
7. Improve installation and release ergonomics, including launcher polish and environment diagnostics.
8. Add more published curve examples if clone-target workflows generate repeated support questions.
9. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
10. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
