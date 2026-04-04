# TASK-078 — Live curve preview in the target editor

## Summary
Render the interpolated target curve in real time as the user edits control points, so they can see the shape before saving.

## Context
The target editor has editable control points with PCHIP interpolation, but the user has no visual feedback — they edit numbers and sliders blind, then save and hope. A live preview on a tkinter Canvas would close the feedback loop.

## Scope
- Add a Canvas widget below or beside the control point list in the target editor view.
- On every "Apply changes" (or on slider drag), evaluate the editor curve and render it as a polyline on the canvas.
- Use log-frequency X axis (20–20000 Hz) and linear dB Y axis (±20 dB).
- Draw a 0 dB reference line and light grid lines at octave boundaries.
- Keep it simple — no interactivity on the canvas itself (drag-on-canvas is a later feature).

## Out of scope
- Drag-to-move points on the canvas (future).
- Comparison overlay with measurement data.
- SVG export of the preview.

## Acceptance criteria
- The target editor shows a live curve that updates when Apply is clicked.
- Flat default shows a flat line at 0 dB.
- A boost at 1 kHz visibly humps the curve.
- Existing GUI tests pass.

## Suggested files
- `headmatch/gui_views.py` (render_target_editor)
- `headmatch/gui.py` (pass evaluated curve data)
