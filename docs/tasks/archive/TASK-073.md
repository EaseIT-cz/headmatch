# TASK-073 — Type-narrow PEQBand.kind to Literal

## Summary
`PEQBand.kind` is typed as `str`, allowing silent misspellings that only manifest at export time. Narrow it to `Literal["peaking", "lowshelf", "highshelf"]`.

## Scope
- Change `PEQBand.kind: str` to `PEQBand.kind: Literal["peaking", "lowshelf", "highshelf"]`.
- Add the `Literal` import.
- Verify all existing code passes type checking (no misspellings exist today, but this prevents future ones).

## Acceptance criteria
- `PEQBand.kind` is type-narrowed.
- Full test suite passes.

## Suggested files
- `headmatch/peq.py`
