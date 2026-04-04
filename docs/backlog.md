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
- Equalizer APO-compatible parametric and GraphicEQ preset export
- CamillaDSP export
- confidence / trust summaries in fit outputs
- fixed-band GraphicEQ fitting support (10-band and 31-band profiles)
- mono and duplicated-channel capture rejection (including multichannel files)

## Active

1. TASK-061: Add confidence badge styling to GUI history view

   Visual differentiation (color/icon) for high/medium/low confidence in
   the history list so users can scan results at a glance.

   Suggested files: `headmatch/gui_views.py`, `headmatch/gui.py`, `tests/test_gui.py`

2. TASK-062: Add one-line confidence verdict to CLI fit output

   Single-line colored pass/fail verdict as the first line of CLI confidence
   output, before the detailed breakdown.

   Suggested files: `headmatch/cli.py`, `tests/test_cli.py`

3. TASK-063: Add GUI setup diagnostics view

   Make the GUI Setup view a proper scrollable diagnostics panel with refresh,
   matching the CLI `headmatch doctor` experience.

   Suggested files: `headmatch/gui.py`, `headmatch/gui_views.py`, `tests/test_gui.py`

## Recently completed (0.2.3)
- TASK-054: Reject mono or duplicated-channel captures during analysis
- TASK-059: Extend duplicated-channel detection to multichannel captures
- TASK-060: Refactor TASK-054 tests to use pytest.raises

## Recently completed (0.2.2)
- TASK-057: Add fixed-band GraphicEQ fitting on top of the shared objective/residual layer
- TASK-058: Expand synthetic regression coverage around fitting/export edge cases

## Recently completed (earlier)
- TASK-056: Add Equalizer APO GraphicEQ export
- TASK-055: Add exact-count PEQ fitting mode
- TASK-053: Add GUI file and folder pickers for path fields

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

1. Add export formats beyond CamillaDSP and APO if users actually need them.
2. Add more published curve examples if clone-target workflows generate repeated support questions.
3. Add real-world recorder fixture coverage if synthetic integration testing is no longer enough.
4. Consider a safe mode vs advanced mode split if the product starts to accumulate too many knobs.
5. Keep the TUI functional, but treat it as maintenance-only unless a clear use case reappears.

## Future feature candidates (deferred)

1. Asynchronous Device Support and Clock Drift Compensation
2. Automated HRTF Target Integration and Scaling
3. Integration of CamillaDSP Live-Updates via WebSocket API
