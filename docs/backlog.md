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

1. Add export formats beyond CamillaDSP if users actually need them.
2. Improve PipeWire device discovery and guidance if users struggle with manual target matching.
3. Add more published curve examples if clone-target workflows generate repeated support questions.
4. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
