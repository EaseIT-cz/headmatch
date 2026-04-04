# TASK-074 — Extract confidence thresholds into named constants

## Summary
`_summarize_trustworthiness` in `pipeline.py` uses magic numbers (0.80, 0.85, 2.5, etc.) for confidence scoring thresholds. Extract them into named constants at the top of the module for clarity and easier tuning.

## Scope
- Identify all numeric thresholds in the confidence scoring function.
- Replace with named constants (e.g., `ALIGNMENT_SCORE_WARNING = 0.80`).
- No logic changes — just readability.

## Acceptance criteria
- All confidence thresholds are named constants.
- Existing confidence tests pass unchanged.

## Suggested files
- `headmatch/pipeline.py`
