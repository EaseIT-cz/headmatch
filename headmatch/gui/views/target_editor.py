# headmatch/gui/views/target_editor.py
"""Target curve editor view rendering."""
from __future__ import annotations

from .common import SECTION_PAD, BODY_WRAP, DETAIL_WRAP


class _PlotGeometry:
    """Coordinate mapping for the curve preview canvas."""
    __slots__ = ('pad_left', 'pad_right', 'pad_top', 'pad_bottom',
                 'plot_w', 'plot_h', 'db_min', 'db_max',
                 'log_min', 'log_max', 'f_min', 'f_max')

    def __init__(self, width, height):
        import math
        self.pad_left, self.pad_right, self.pad_top, self.pad_bottom = 45, 15, 15, 25
        self.plot_w = width - self.pad_left - self.pad_right
        self.plot_h = height - self.pad_top - self.pad_bottom
        self.db_min, self.db_max = -20.0, 20.0
        self.f_min, self.f_max = 20.0, 20000.0
        self.log_min = math.log10(self.f_min)
        self.log_max = math.log10(self.f_max)

    def freq_to_x(self, f):
        import math
        return self.pad_left + (math.log10(max(f, self.f_min)) - self.log_min) / (self.log_max - self.log_min) * self.plot_w

    def db_to_y(self, db):
        return self.pad_top + (self.db_max - db) / (self.db_max - self.db_min) * self.plot_h

    def x_to_freq(self, x):
        ratio = (x - self.pad_left) / self.plot_w
        ratio = max(0.0, min(1.0, ratio))
        log_f = self.log_min + ratio * (self.log_max - self.log_min)
        return max(self.f_min, min(self.f_max, 10 ** log_f))

    def y_to_db(self, y):
        ratio = (y - self.pad_top) / self.plot_h
        ratio = max(0.0, min(1.0, ratio))
        return self.db_max - ratio * (self.db_max - self.db_min)


def _plot_geometry(width=560, height=200):
    return _PlotGeometry(width, height)


def _render_curve_preview(canvas, editor, width=560, height=200):
    """Draw the interpolated target curve on a tkinter Canvas.

    X axis: log-frequency 20–20000 Hz
    Y axis: linear dB, ±20 dB range

    Returns a PlotGeometry namedtuple for coordinate conversion (used by drag handlers).
    """
    import math

    canvas.delete("all")

    geom = _plot_geometry(width, height)

    # Background
    canvas.create_rectangle(geom.pad_left, geom.pad_top,
                           geom.pad_left + geom.plot_w, geom.pad_top + geom.plot_h,
                           fill="#1a1a2e", outline="#333355")

    # Grid lines — octave boundaries
    grid_color = "#2a2a4e"
    label_color = "#888899"
    octave_freqs = [31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    for f in octave_freqs:
        x = geom.freq_to_x(f)
        canvas.create_line(x, geom.pad_top, x, geom.pad_top + geom.plot_h, fill=grid_color, dash=(2, 4))
        label = f"{f/1000:g}k" if f >= 1000 else f"{f:g}"
        canvas.create_text(x, geom.pad_top + geom.plot_h + 12, text=label, fill=label_color, font=("TkDefaultFont", 7))

    # Horizontal dB grid lines
    for db in [-15, -10, -5, 0, 5, 10, 15]:
        y = geom.db_to_y(db)
        color = "#444466" if db == 0 else grid_color
        width_line = 1.5 if db == 0 else 1
        canvas.create_line(geom.pad_left, y, geom.pad_left + geom.plot_w, y, fill=color, width=width_line,
                          dash=() if db == 0 else (2, 4))
        canvas.create_text(geom.pad_left - 5, y, text=f"{db:+d}", anchor="e", fill=label_color, font=("TkDefaultFont", 7))

    # Evaluate and draw curve
    import numpy as np
    try:
        freqs, values = editor.evaluate()
        if len(freqs) < 2:
            return geom

        coords = []
        for f, v in zip(freqs, values):
            x = geom.freq_to_x(float(f))
            y = geom.db_to_y(float(max(geom.db_min, min(geom.db_max, v))))
            coords.extend([x, y])

        if len(coords) >= 4:
            canvas.create_line(*coords, fill="#00ccaa", width=2, smooth=True, tags="curve_line")

        # Draw control points with tags for drag binding
        r = 5
        for i, point in enumerate(editor.points):
            px = geom.freq_to_x(point.freq_hz)
            py = geom.db_to_y(max(geom.db_min, min(geom.db_max, point.gain_db)))
            tag = f"cp_{i}"
            canvas.create_oval(px - r, py - r, px + r, py + r, fill="#55aaff", outline="#88ccff", tags=(tag, "control_point"))
        return geom
    except Exception:
        return geom


def render_target_editor(ttk, frame, *, editor, on_save, on_reset, on_load=None, on_update=None):
    """Render the target curve editor interface.

    Parameters
    ----------
    ttk : module
        The ttk module from tkinter
    frame : tkinter.Frame
        Parent frame to render into
    editor : TargetEditor
        The target editor model object
    on_save : callable
        Callback when user clicks Save
    on_reset : callable
        Callback when user clicks Reset
    on_load : callable, optional
        Callback when user clicks Load
    on_update : callable, optional
        Callback when curve is modified
    """
    import tkinter as tk  # Canvas, DoubleVar are in tkinter, not ttk

    _vars = {"setup_done": False, "gain_scales": []}

    # Scrollable canvas for the curve preview
    preview_frame = ttk.LabelFrame(frame, text="Curve preview (drag points)", padding=SECTION_PAD)
    preview_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    preview_frame.columnconfigure(0, weight=1)

    canvas = tk.Canvas(preview_frame, width=560, height=200, bg="#1a1a2e", highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="ew")

    def _redraw():
        geom = _render_curve_preview(canvas, editor)
        return geom

    geom = _redraw()

    # Drag handling
    _drag = {"active": None, "start_y": None}

    def _on_press(event, geom=geom):
        tags = canvas.gettags(canvas.find_closest(event.x, event.y)[0])
        for t in tags:
            if t.startswith("cp_"):
                _drag["active"] = int(t.split("_")[1])
                _drag["start_y"] = event.y
                break

    def _on_drag(event, geom=geom):
        if _drag["active"] is not None:
            new_db = geom.y_to_db(event.y)
            new_db = max(-20.0, min(20.0, new_db))
            pt = editor.points[_drag["active"]]
            editor.update_point(_drag["active"], pt.freq_hz, new_db)
            editor.interpolate()
            _redraw()
            if on_update:
                on_update()

    def _on_release(event):
        _drag["active"] = None
        _drag["start_y"] = None

    canvas.bind("<Button-1>", _on_press)
    canvas.bind("<B1-Motion>", _on_drag)
    canvas.bind("<ButtonRelease-1>", _on_release)

    # Points list with editable frequencies/gains
    points_frame = ttk.LabelFrame(frame, text="Control points", padding=SECTION_PAD)
    points_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    points_frame.columnconfigure(1, weight=1)

    ttk.Label(points_frame, text="Freq (Hz)").grid(row=0, column=0, sticky="w", padx=(0, 8))
    ttk.Label(points_frame, text="Gain (dB)").grid(row=0, column=1, sticky="w")

    def _sync_editor_and_redraw():
        # Sync scale values back to editor points
        for i, scale in enumerate(_vars["gain_scales"]):
            if i < len(editor.points):
                pt = editor.points[i]
                editor.update_point(i, pt.freq_hz, scale.get())
        editor.interpolate()
        _redraw()

    def _remove_point(idx):
        if len(editor.points) > 2:
            editor.remove_point(idx)
            _rebuild_points_list()
            if on_update:
                on_update()

    def _rebuild_points_list():
        # Clear existing widgets
        for widget in points_frame.winfo_children():
            if int(widget.grid_info().get("row", 0)) > 0:
                widget.destroy()
        _vars["gain_scales"] = []

        for idx, point in enumerate(editor.points):
            row = idx + 1

            # Frequency label (read-only for simplicity)
            ttk.Label(points_frame, text=f"{point.freq_hz:.1f}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)

            # Gain scale
            gain_var = tk.DoubleVar(value=point.gain_db)
            gain_scale = ttk.Scale(points_frame, from_=-20, to=20, variable=gain_var, orient="horizontal")
            gain_scale.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=2)
            _vars["gain_scales"].append(gain_scale)

            # Add point button
            def _add_after(i=idx):
                pts = editor.points
                if i < len(pts) - 1:
                    new_freq = (pts[i].freq_hz + pts[i + 1].freq_hz) / 2
                    new_gain = (pts[i].gain_db + pts[i + 1].gain_db) / 2
                else:
                    new_freq = min(pts[i].freq_hz * 1.5, 20000.0)
                    new_gain = pts[i].gain_db
                editor.add_point(new_freq, new_gain)
                if on_update:
                    on_update()

            ttk.Button(points_frame, text="+", command=_add_after, width=3).grid(
                row=row, column=3, sticky="w", pady=2)
            if len(editor.points) > 2:
                ttk.Button(points_frame, text="\u2715", command=lambda i=idx: _remove_point(i), width=3).grid(
                    row=row, column=4, sticky="w", pady=2)

    _rebuild_points_list()
    _vars["setup_done"] = True

    # Action buttons
    actions = ttk.Frame(frame, padding=(0, 8, 0, 0))
    actions.grid(row=4, column=0, sticky="w")
    col = 0
    ttk.Button(actions, text="Save as CSV", command=lambda: [_sync_editor_and_redraw(), on_save()]).grid(
        row=0, column=col, sticky="w")
    col += 1
    if on_load:
        ttk.Button(actions, text="Load CSV", command=on_load).grid(row=0, column=col, sticky="w", padx=(12, 0))
        col += 1
    ttk.Button(actions, text="Reset to flat", command=on_reset).grid(row=0, column=col, sticky="w", padx=(12, 0))
    ttk.Label(
        actions,
        text="After saving, use the CSV as --target-csv in your next measurement or fit.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=1, column=0, columnspan=col + 1, sticky="w", pady=(8, 0))


__all__ = ['_PlotGeometry', '_plot_geometry', '_render_curve_preview', 'render_target_editor']
