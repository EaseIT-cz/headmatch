# TASK-095: Feature – Clipping assessment

**Summary**: Implement clipping prediction when assessing measurement quality.

**Context**: Users need to know if recorded audio is clipping, which affects EQ fitting accuracy.

**Scope**:
- Add logic to detect clipping in the audio buffer during measurement.
- Expose a confidence metric or warning in the GUI and CLI output.
- Update documentation to describe the new metric.

**Out‑of‑Scope**:
- Automatic gain reduction or post‑processing to fix clipping.
- Advanced multi‑channel clipping analysis.

**Acceptance Criteria**:
- Clipping detection runs during measurement and sets a flag if any sample exceeds a configurable threshold (e.g., 0 dBFS).
- GUI shows a warning icon/message when clipping is detected.
- CLI prints a “Clipping detected” line in the summary.
- Unit tests cover clipping detection cases.

**Suggested Files/Components**:
- `headmatch/measure.py` (add clipping check)
- `headmatch/gui.py` (display warning)
- `headmatch/cli.py` (output flag)
- Documentation update (`docs/feature_clipping.md`).
