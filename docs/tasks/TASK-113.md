# TASK-113 - Document confidence scoring derivation

## Summary
Add documentation explaining the empirical basis for confidence scoring thresholds and weights in `pipeline_confidence.py`.

## Context
The confidence scoring system uses magic numbers (ALIGNMENT_SCORE_WARN=0.85, ROUGHNESS_WARN_DB=3.0, etc.) without explaining how they were derived. This makes it difficult to tune or validate the system.

## Scope
- Add docstrings to confidence constants explaining derivation
- Optionally add a design document in `docs/`
- Document the relationship between thresholds and scoring outcomes
- Include rationale for weight values

## Out of scope
- Changing threshold values
- Rewriting scoring algorithm
- Adding new scoring factors

## Acceptance criteria
- Each constant has a docstring explaining its derivation
- Design document exists or module docstring is comprehensive
- Values are justified by measurement experience or theory

## Suggested files/components
- `headmatch/pipeline_confidence.py`
- `docs/confidence-scoring.md` (optional)
