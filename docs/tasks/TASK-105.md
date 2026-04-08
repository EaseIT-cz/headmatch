# TASK-105: EQ Clipping CLI Output

## Summary
Add clipping assessment summary to CLI fit output so users see preamp recommendations in terminal.

## Context
`assess_eq_clipping()` runs automatically during fitting. CLI currently only shows confidence verdict, not clipping info.

## Scope
- Add clipping section to `headmatch fit` output
- Display after confidence summary:
  - Preamp recommendation
  - Max boost level
  - Warning if headroom loss significant
- Add `--show-clipping` flag for detailed breakdown
- Include clipping data in JSON output (`--json`)

## Out of Scope
- Changing clipping algorithm
- GUI display (separate task)
- Auto-applying preamp

## Acceptance Criteria
- [ ] `headmatch fit` shows clipping summary when present
- [ ] `--show-clipping` flag provides detailed breakdown
- [ ] JSON output includes clipping assessment object
- [ ] Help text updated

## Suggested Files
- `headmatch/cli.py`
- `headmatch/pipeline.py` — clipping data flow