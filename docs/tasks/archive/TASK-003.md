# TASK-003 — Improve output structure and run summaries

## Summary
Make generated folders and reports easier for audiophile users to understand.

## Context
Current outputs are functional but developer-centric. The audience should be able to open a run folder and immediately know what happened and what to do next.

## Scope
- Review generated artifact names and folder layout.
- Add concise run summary metadata.
- Add a friendly next-step summary to fit reports.
- Keep filenames predictable and stable.

## Out of scope
- Measurement algorithm changes.
- New export formats.

## Acceptance criteria
- Output folders are self-explanatory.
- Reports contain a plain-language summary.
- The main artifacts are easy to locate.
- Existing tests still pass.

## Suggested files/components
- `headmatch/pipeline.py`
- `headmatch/io_utils.py`
- `headmatch/exporters.py`
- `README.md`
