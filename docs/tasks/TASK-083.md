# TASK-083 — Split pipeline.py into fit / artifacts / confidence modules

## Summary
Extract the repeated artifact-writing logic and confidence scoring from `pipeline.py` into separate modules. Keep the public orchestration API stable.

## Context
`pipeline.py` (~547 lines) currently mixes fitting orchestration, artifact writing (README, JSON, SVGs, exports), and confidence scoring heuristics. Single-fit and iterative paths repeat the same writing logic. This was already flagged in `docs/architecture.md` as a targeted refactor. Multiple reviews confirm it's now justified — it reduces merge conflicts and makes unit testing easier.

## Scope
- Extract artifact writing into `headmatch/pipeline_artifacts.py`:
  - `write_fit_artifacts(result, out_dir, ...)` — README, summary JSON, fit report, SVGs, export presets
  - Shared by single-fit and iterative paths
- Extract confidence scoring into `headmatch/pipeline_confidence.py`:
  - Scoring logic, threshold constants, message generation
- Keep `headmatch/pipeline.py` as the orchestrator:
  - measure → fit → call artifact writer → call confidence scorer
  - Public API unchanged
- Update imports in CLI/GUI/TUI if any reach into pipeline internals

## Out of scope
- Changing output filenames, summary schema, or artifact content
- GUI refactor (separate task)
- Changing the confidence scoring algorithm

## Acceptance criteria
- All existing pipeline and integration tests pass without modification
- `pipeline.py` is reduced by ~150-200 lines
- No output format changes (byte-identical artifacts for the same input)
- New modules have docstrings explaining their role

## Suggested files
- `headmatch/pipeline.py` (extract from)
- `headmatch/pipeline_artifacts.py` (new)
- `headmatch/pipeline_confidence.py` (new)
- `tests/test_pipeline.py` (verify unchanged behavior)
