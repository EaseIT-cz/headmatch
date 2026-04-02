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

1. Add GraphicEQ export for Equalizer APO on top of the shared objective layer.
2. Keep the design compatible with a later fixed-band / GraphicEQ fitting mode without rewriting the objective/residual logic.

## Recently completed

- surfaced confidence and interpretation more clearly in the GUI and CLI
- reduced duplicated fit artifact writing in `pipeline.py`
- split the GUI shell from view-rendering concerns
- strengthened typed confidence/run-summary contracts
- added conservative troubleshooting guidance tied to low-confidence results
- improved PipeWire target guidance in the CLI and GUI
- added a first GUI run-comparison slice in history
- added a first CLI environment diagnostics command (`headmatch doctor`)
- added GUI setup checks, target dropdowns, and navigation/layout cleanup
- expanded examples/docs for targets and clone-target workflows
- corrected clone-target backend semantics so relative targets are handled correctly during fitting
- fixed PEQ filter-budget handling
- added package-build, release-asset, and PyPI publish GitHub Actions workflows
- updated docs so PyPI install is the primary user path

## Future follow-up candidates

1. Add GraphicEQ export / fixed-band fitting on top of the shared objective layer.
2. Add export formats beyond CamillaDSP and APO if users actually need them.
3. Add more published curve examples if clone-target workflows generate repeated support questions.
4. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
5. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
6. Keep the TUI functional, but treat it as maintenance-only unless a clear use case reappears.
