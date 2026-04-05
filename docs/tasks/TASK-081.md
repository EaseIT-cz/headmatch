# TASK-081 — Make shelf-band parameter semantics explicit

## Summary
The `PEQBand.q` field is overloaded: it means Q for peaking filters but slope S for shelves. Add explicit semantics to prevent future contributor mistakes and exporter drift.

## Context
Multiple code reviews flagged this as a maintainability hazard. The shelf S→Q conversion happens in `exporters.py` for CamillaDSP output, but the data model doesn't distinguish the two meanings. A future contributor who assumes `q` always means Q will break shelf behavior silently.

The fix is internal — no user-facing behavior change, no file format change.

## Scope
- Add a `slope: float | None = None` field to `PEQBand` (or equivalent mechanism)
- For `kind in {lowshelf, highshelf}`: store slope in `slope`, keep `q` as a computed property that returns the converted Q value
- For `kind == peaking`: `slope` stays None, `q` behaves as today
- Update `peq.py` shelf fitting code to populate `slope` instead of `q`
- Update `exporters.py` to read `slope` directly for shelves instead of re-converting from `q`
- Add backward compatibility: if a PEQBand is created with `q` and shelf kind but no `slope`, treat `q` as slope (legacy path)
- Add docstrings explaining the distinction

## Out of scope
- Changing exported file formats
- Changing CLI/GUI user-facing parameter names
- APO import changes (separate task if needed)

## Acceptance criteria
- All existing tests pass without modification (backward compat)
- New unit tests verify:
  - Peaking band: `slope is None`, `q` is Q
  - Shelf band: `slope` is populated, `q` returns converted Q
  - Legacy shelf construction (q only, no slope) still works
- Round-trip test: shelf band → CamillaDSP export → re-import produces same parameters
- `exporters.py` no longer does its own S→Q conversion (reads from the band directly)

## Suggested files
- `headmatch/peq.py` (PEQBand dataclass, shelf fitting)
- `headmatch/exporters.py` (shelf Q conversion)
- `tests/test_peq.py` (new semantics tests)
- `tests/test_exporters.py` (round-trip test)
