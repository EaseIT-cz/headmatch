# TASK-103: Clone-Target Calibration Documentation

## Summary
Document the clone-target workflow as a mic calibration technique, making it discoverable for users with binaural measurement rigs.

## Context
Binaural microphones don't have flat response. They color measurements. However, if you measure a reference headphone and use that as a calibration target, the mic's coloration cancels out when measuring other headphones against that target.

This workflow exists in the tool but isn't documented as a calibration method.

## Scope
- Add "Mic Calibration" section to README.md
- Add "Clone-Target Calibration" guide to docs/examples/
- Update architecture.md with calibration strategy
- Document recommended workflow:
  1. Choose a reference headphone with published measurements
  2. Measure it with your rig
  3. Save as calibration target
  4. Measure other headphones against this target
- Explain limitations:
  - Calibration only valid for same rig/head combo
  - Differences in seal/position still matter
  - Reference headphone should be well-measured in literature

## Out of Scope
- GUI changes
- Automated calibration curve derivation
- New CLI commands

## Acceptance Criteria
- [ ] README has brief mention of calibration via clone-target
- [ ] New guide file in docs/examples/ with step-by-step workflow
- [ ] Architecture updated with calibration approach breakdown

## Suggested Files
- `README.md`
- `docs/examples/clone-target-calibration.md` (new)
- `docs/architecture.md`