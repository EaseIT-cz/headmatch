# TASK-049 — Document the personal clone-target workflow clearly

## Summary
Clarify how users actually get from measuring two headphones to generating an EQ preset that moves one toward the other, using their own measurements rather than only lightweight published examples.

## Context
The current clone-target docs are still confusing in practice. Users reasonably expect to be able to measure headphone A and headphone B on the same rig, compute the difference, and use that difference to tune headphone A toward headphone B. That workflow is valid, but it is not documented clearly enough today.

## Scope
- Document the preferred personal clone workflow clearly.
- Distinguish it from the lighter published-example clone workflow.
- Explain which output CSVs users should feed into `headmatch clone-target`.
- Add examples that show the full path from two measurements to a clone-target fit.
- Update tests if needed.

## Out of scope
- New backend clone-target features.
- GUI clone-target wizard work.
- New DSP or measurement logic.
- Broad product redesign.

## Acceptance criteria
- README and clone-target example docs clearly explain the personal clone workflow.
- Users can tell which CSV artifacts from their runs should be used as source and target inputs.
- The difference between personal-measurement clone targets and lightweight published examples is explicit.
- The docs reduce ambiguity about how to reach the desired result.

## Suggested files/components
- `README.md`
- `docs/examples/clone-targets/README.md`
- tests/docs assertions only if useful
