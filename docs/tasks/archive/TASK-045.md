# TASK-045 — Add PipeWire device dropdowns to the GUI measurement flow

## Summary
Improve the GUI measurement flow by populating playback and capture target fields from available PipeWire devices and presenting them as dropdown selections.

## Context
The current GUI still expects manual text entry for PipeWire playback/capture targets. The next user-facing improvement is to make those fields easier and safer to use by offering real device choices. Preferred default behavior:
- use the configured target from saved config when present
- otherwise use the current OS default device when available

The user specifically called out `wpctl status` as the desired source for the active/default device context.

## Scope
- Replace the manual playback/capture target entry fields in the GUI measurement flow with dropdown selections.
- Populate those selections from available PipeWire devices.
- Default selection priority:
  1. saved config target, if present and available
  2. current OS default device, if available
  3. otherwise a sensible first discovered option or empty selection
- Keep the implementation GUI-focused and practical.
- Update tests as needed.

## Out of scope
- Broad PipeWire backend redesign.
- CLI or TUI changes.
- New measurement behavior beyond selecting targets.
- Major GUI redesign.

## Acceptance criteria
- GUI users can choose playback/capture targets from dropdowns instead of raw text entry.
- Available devices are populated from PipeWire discovery.
- Configured targets are respected when available.
- If no configured override exists, OS defaults are used when discoverable.
- Full test suite passes.

## Suggested files/components
- `headmatch/measure.py`
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
- `tests/test_measure.py`
