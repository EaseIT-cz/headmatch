from __future__ import annotations

from .common import (
    SECTION_PAD,
    BODY_WRAP,
    DETAIL_WRAP,
)

__all__ = ['_PlotGeometry', '_plot_geometry', '_render_curve_preview', 'render_target_editor']


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
            canvas.create_oval(px - r, py - r, px + r, py + r,
                              fill="#ff6644", outline="#ffaa88", width=1, tags=(tag, "control_point"))
    except Exception:
        pass  # Don't crash the GUI on eval errors

    return geom


def render_target_editor(ttk, frame, *, editor, on_save, on_reset, on_load=None, on_update=None):
    """Render an interactive target curve editor with live-updating preview."""
    import tkinter as tk

    ttk.Label(frame, text="Target curve editor", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Drag points on the graph, use sliders, or type values. Everything updates live.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    # Curve preview canvas — placed above the controls for immediate feedback
    preview_frame = ttk.LabelFrame(frame, text="Curve preview", padding=4)
    preview_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    canvas = tk.Canvas(preview_frame, width=560, height=200, bg="#1a1a2e", highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="ew")
    _geom = [_render_curve_preview(canvas, editor)]  # mutable box for geometry
    _drag_idx = [None]  # index of control point being dragged

    # ── Live update helpers ──

    # Mutable container so closures always see the latest lists
    _vars = {"freq": [], "gain": [], "gain_labels": [], "gain_scales": [], "setup_done": False}

    def _sync_editor_and_redraw():
        """Read all widget values into the editor model and redraw."""
        if not _vars["setup_done"]:
            return
        for i, (fv, gv) in enumerate(zip(_vars["freq"], _vars["gain"])):
            try:
                freq = float(fv.get())
                gain = float(gv.get())
                if i < len(editor.points):
                    editor.move_point(i, max(20.0, min(20000.0, freq)), max(-20.0, min(20.0, gain)))
            except (ValueError, IndexError):
                pass
        _geom[0] = _render_curve_preview(canvas, editor)

    def _on_slider_change(val, gvar, glabel):
        """Called on every slider tick — update the gain var, label, and redraw."""
        rounded = f"{float(val):.1f}"
        gvar.set(rounded)
        glabel.config(text=f"{rounded} dB")
        if _vars["setup_done"]:
            _sync_editor_and_redraw()

    def _on_entry_commit(_event=None):
        """Called on Return or FocusOut from any entry."""
        _sync_editor_and_redraw()

    # ── Canvas drag handlers ──
    # Bound to the canvas itself (not individual items) so drag survives redraws.

    def _on_drag_start(event):
        """Find the closest control point within grab radius."""
        geom = _geom[0]
        if geom is None:
            return
        closest_idx, closest_dist = None, 14  # grab radius in pixels
        for i, point in enumerate(editor.points):
            px = geom.freq_to_x(point.freq_hz)
            py = geom.db_to_y(max(geom.db_min, min(geom.db_max, point.gain_db)))
            dist = ((event.x - px) ** 2 + (event.y - py) ** 2) ** 0.5
            if dist < closest_dist:
                closest_idx, closest_dist = i, dist
        _drag_idx[0] = closest_idx

    def _on_drag_motion(event):
        """Move the dragged control point to cursor position (lightweight redraw)."""
        idx = _drag_idx[0]
        if idx is None:
            return
        geom = _geom[0]
        if geom is None:
            return
        freq = max(20.0, min(20000.0, geom.x_to_freq(event.x)))
        gain = max(-20.0, min(20.0, geom.y_to_db(event.y)))

        # Update the editor model — but move_point re-sorts, so track by identity
        old_point = editor.points[idx]
        editor.points[idx] = type(old_point)(freq, gain)
        editor.points.sort(key=lambda p: p.freq_hz)
        # Find the new index after sort
        new_idx = next(i for i, p in enumerate(editor.points)
                       if p.freq_hz == freq and p.gain_db == gain)
        _drag_idx[0] = new_idx

        # Lightweight canvas update: delete curve + points, redraw them
        canvas.delete("curve_line")
        canvas.delete("control_point")

        import numpy as np
        try:
            freqs, values = editor.evaluate()
            if len(freqs) >= 2:
                coords = []
                for f, v in zip(freqs, values):
                    x = geom.freq_to_x(float(f))
                    y = geom.db_to_y(float(max(geom.db_min, min(geom.db_max, v))))
                    coords.extend([x, y])
                if len(coords) >= 4:
                    canvas.create_line(*coords, fill="#00ccaa", width=2, smooth=True, tags="curve_line")
        except Exception:
            pass

        r = 5
        for i, point in enumerate(editor.points):
            px = geom.freq_to_x(point.freq_hz)
            py = geom.db_to_y(max(geom.db_min, min(geom.db_max, point.gain_db)))
            fill = "#ffcc00" if i == new_idx else "#ff6644"
            canvas.create_oval(px - r, py - r, px + r, py + r,
                              fill=fill, outline="#ffaa88", width=1, tags="control_point")

    def _on_drag_end(_event):
        """Finalize drag: do a full redraw and sync widgets."""
        idx = _drag_idx[0]
        _drag_idx[0] = None
        if idx is None:
            return
        # Full redraw to get clean state
        _geom[0] = _render_curve_preview(canvas, editor)
        # Sync widgets to match final editor state
        if _vars["setup_done"]:
            for i, point in enumerate(editor.points):
                if i < len(_vars["freq"]):
                    _vars["freq"][i].set(f"{point.freq_hz:.0f}")
                    _vars["gain"][i].set(f"{point.gain_db:.1f}")
                if i < len(_vars["gain_labels"]):
                    _vars["gain_labels"][i].config(text=f"{point.gain_db:.1f} dB")
                if i < len(_vars["gain_scales"]):
                    try:
                        _vars["setup_done"] = False  # suppress sync during set()
                        _vars["gain_scales"][i].set(point.gain_db)
                        _vars["setup_done"] = True
                    except Exception:
                        _vars["setup_done"] = True

    canvas.bind("<ButtonPress-1>", _on_drag_start)
    canvas.bind("<B1-Motion>", _on_drag_motion)
    canvas.bind("<ButtonRelease-1>", _on_drag_end)

    # ── Control points table ──

    points_outer = ttk.LabelFrame(frame, text="Control points", padding=SECTION_PAD)
    points_outer.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
    points_outer.columnconfigure(0, weight=1)
    points_outer.rowconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Use a scrollable canvas wrapper when there are many points
    if len(editor.points) > 8:
        _scroll_canvas = tk.Canvas(points_outer, highlightthickness=0, height=220)
        _scroll_canvas.grid(row=0, column=0, sticky="nsew")
        _scrollbar = ttk.Scrollbar(points_outer, orient="vertical", command=_scroll_canvas.yview)
        _scrollbar.grid(row=0, column=1, sticky="ns")
        _scroll_canvas.configure(yscrollcommand=_scrollbar.set)
        points_frame = ttk.Frame(_scroll_canvas)
        _scroll_win = _scroll_canvas.create_window((0, 0), window=points_frame, anchor="nw")
        def _on_points_configure(_event=None):
            _scroll_canvas.configure(scrollregion=_scroll_canvas.bbox("all"))
        def _on_canvas_configure(event):
            _scroll_canvas.itemconfigure(_scroll_win, width=event.width)
        points_frame.bind("<Configure>", _on_points_configure)
        _scroll_canvas.bind("<Configure>", _on_canvas_configure)
    else:
        points_frame = ttk.Frame(points_outer)
        points_frame.grid(row=0, column=0, sticky="nsew")
    points_frame.columnconfigure(1, weight=1)

    # Header row
    ttk.Label(points_frame, text="Freq (Hz)", style="Heading.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
    ttk.Label(points_frame, text="Gain", style="Heading.TLabel").grid(row=0, column=1, sticky="w", padx=(0, 8))
    ttk.Label(points_frame, text="dB", style="Heading.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))

    def _remove_point(idx):
        editor.remove_point(idx)
        if on_update:
            on_update()

    for idx, point in enumerate(editor.points):
        row = idx + 1
        fv = tk.StringVar(value=f"{point.freq_hz:.0f}")
        gv = tk.StringVar(value=f"{point.gain_db:.1f}")
        _vars["freq"].append(fv)
        _vars["gain"].append(gv)

        # Frequency entry
        freq_entry = ttk.Entry(points_frame, textvariable=fv, width=8)
        freq_entry.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        freq_entry.bind("<Return>", _on_entry_commit)
        freq_entry.bind("<FocusOut>", _on_entry_commit)

        # Gain label (shows current dB value, updated by slider)
        gain_label = ttk.Label(points_frame, text=f"{point.gain_db:.1f} dB", width=8)
        gain_label.grid(row=row, column=2, sticky="w", padx=(0, 4), pady=2)
        _vars["gain_labels"].append(gain_label)

        # Gain slider — the primary input
        gain_scale = ttk.Scale(
            points_frame, from_=-20.0, to=20.0, orient="horizontal",
            command=lambda val, _gv=gv, _gl=gain_label: _on_slider_change(val, _gv, _gl),
        )
        try:
            gain_scale.set(point.gain_db)
        except Exception:
            pass
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
            ttk.Button(points_frame, text="X", command=lambda i=idx: _remove_point(i), width=3).grid(
                row=row, column=4, sticky="w", pady=2)

    _vars["setup_done"] = True

    # ── Action buttons ──

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