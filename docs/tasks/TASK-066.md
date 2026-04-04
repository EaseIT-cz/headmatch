# TASK-066 — Display fit SVG graphs in the GUI results view

## Summary
HeadMatch generates measured-vs-target SVG review graphs in every fit output folder. The GUI history view shows metadata and confidence but never displays the actual graphs. Add inline SVG rendering to the results view.

## Context
`plots.py` generates SVG files via `render_fit_graphs`. These are written to the output folder alongside other artifacts. The GUI `render_history_results` in `gui_views.py` shows confidence, summary text, and comparison tables — but no visual graphs.

For a measurement tool, the graph is the most important artifact. Users should see it without leaving the GUI.

## Scope
- In the selected-run detail section of the history view, render the fit SVG graph(s) inline.
- tkinter doesn't natively render SVG. Options:
  - Convert SVG to PNG at display time using a lightweight library (cairosvg, svglib+reportlab) — adds a dependency.
  - Use tkinter's Canvas to render a simplified version — complex, fragile.
  - Embed the SVG in a tkinter.Text widget as an image after rasterizing — simplest if a rasterizer is available.
  - Fall back to a "Open graph" button that launches the SVG in the system's default viewer (`xdg-open`) — zero-dependency fallback.
- Prefer the zero-dependency fallback as primary, with optional inline rendering if a rasterizer is detected.

## Out of scope
- Changing the SVG generation in `plots.py`.
- Interactive graph manipulation (zoom, hover values).
- Adding mandatory new dependencies.

## Acceptance criteria
- The GUI results view shows a clickable button to open the fit graph in the system viewer.
- If an optional rasterizer library is available, graphs are shown inline.
- Missing graph files are handled gracefully (no crash, shows "Graph not available").
- Existing GUI tests pass.

## Suggested files/components
- `headmatch/gui_views.py`
- `headmatch/gui.py`
- `tests/test_gui.py`
