# TASK-076 — Make FitObjective.weights configurable

## Summary
`FitObjective.from_target` hardcodes `_residual_priority_weights` internally. Different use cases (headphone, speaker, sub-bass correction) need different weighting profiles. Make the weights injectable.

## Scope
- Add an optional `weights` parameter to `FitObjective.from_target`.
- If not provided, use the current `_residual_priority_weights` as default.
- Keep the existing weighting profile as the documented default for headphone EQ.

## Out of scope
- Defining alternative weighting profiles (future work).
- Changing the default behaviour.

## Acceptance criteria
- `FitObjective.from_target` accepts an optional weights array.
- Default behaviour is unchanged.
- Full test suite passes.

## Suggested files
- `headmatch/peq.py`
- `tests/test_peq_exporters.py`
