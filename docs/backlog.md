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

## Future follow-up candidates

These are not active tasks yet. They are the most likely next areas of work.

1. Add measured-vs-target graph generation so users can visually compare raw measurement, target curve, and fitted result.
2. Add export formats beyond CamillaDSP if users actually need them.
3. Improve PipeWire device discovery and guidance if users struggle with manual target matching.
4. Add result interpretation and confidence scoring so users can tell whether a run is trustworthy.
5. Add a guided troubleshooting flow for common setup and measurement failures.
6. Add preset/run comparison workflows so users can compare stock, corrected, and clone-target results more easily.
7. Improve installation and release ergonomics, including launcher polish and environment diagnostics.
8. Add more published curve examples if clone-target workflows generate repeated support questions.
9. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
10. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
