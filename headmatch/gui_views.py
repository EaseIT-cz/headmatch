from __future__ import annotations

from pathlib import Path

from .history import build_history_selection
import subprocess
import sys
from .troubleshooting import confidence_troubleshooting_steps


ONLINE_STEPS = (
    "Check the output folder and saved PipeWire targets.",
    "Playback target = the DAC, headphones, speakers, or interface output that should play the sweep.",
    "Capture target = the mic, recorder, or interface input that should hear it.",
    "If you are unsure, run 'headmatch list-targets' first and paste the exact node names.",
    "Press Start when your rig is ready.",
    "HeadMatch runs the shared online pipeline and then shows the output folder.",
)


OFFLINE_STEPS = (
    "Write a sweep package if you need to record with a handheld recorder first.",
    "After recording, point the GUI at the WAV file and run the offline fit.",
    "Both actions reuse the shared sweep and fitting pipeline.",
)



SECTION_PAD = 12
FIELD_PAD_Y = 3
BODY_WRAP = 560
DETAIL_WRAP = 520
COMPARISON_WRAP = 240


def add_readonly_row(ttk, parent, row: int, label: str, variable) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=FIELD_PAD_Y)
    entry = ttk.Entry(parent, textvariable=variable)
    entry.state(["readonly"])
    entry.grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)


def add_combobox_row(ttk, parent, row: int, label: str, variable, values: tuple[str, ...], *, empty_label: str) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=FIELD_PAD_Y)
    state = "readonly" if values else "normal"
    combo = ttk.Combobox(parent, textvariable=variable, values=values, state=state)
    combo.grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)
    if not values and not variable.get().strip():
        combo.set("")


def add_entry_row(ttk, parent, row: int, label: str, variable) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=FIELD_PAD_Y)
    ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)


def add_picker_row(ttk, parent, row: int, label: str, variable, *, button_text: str, command) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=FIELD_PAD_Y)
    entry_frame = ttk.Frame(parent)
    entry_frame.grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)
    entry_frame.columnconfigure(0, weight=1)
    ttk.Entry(entry_frame, textvariable=variable).grid(row=0, column=0, sticky="ew")
    ttk.Button(entry_frame, text=button_text, command=command).grid(row=0, column=1, sticky="w", padx=(8, 0))


def render_online_wizard(ttk, frame, *, variables, on_start) -> None:
    ttk.Label(frame, text="Online measurement wizard", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Use this when PipeWire playback and capture are available now. Choose the output that should play the sweep and the input that should hear it.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ttk.LabelFrame(frame, text="What happens", padding=SECTION_PAD)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(ONLINE_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    form = ttk.LabelFrame(frame, text="Run details", padding=SECTION_PAD)
    form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    form.columnconfigure(1, weight=1)
    add_picker_row(ttk, form, 0, "Output folder", variables.output_dir_var, button_text="Browse…", command=variables.choose_output_dir)
    add_combobox_row(ttk, form, 1, "Playback target", variables.output_target_var, variables.output_target_options, empty_label="No playback targets found")
    add_combobox_row(ttk, form, 2, "Capture target", variables.input_target_var, variables.input_target_options, empty_label="No capture targets found")
    add_picker_row(ttk, form, 3, "Target CSV (optional)", variables.target_csv_var, button_text="Browse…", command=variables.choose_target_csv)
    add_entry_row(ttk, form, 4, "Iterations", variables.iterations_var)
    add_entry_row(ttk, form, 5, "Max PEQ filters", variables.max_filters_var)
    add_combobox_row(ttk, form, 6, "Iteration mode", variables.iteration_mode_var, ("independent", "average"), empty_label="")

    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=4, column=0, sticky="w")
    ttk.Button(actions, text="Start guided measurement", command=on_start).grid(row=0, column=0, sticky="w")
    ttk.Label(
        actions,
        text="Rig ready and room quiet. Need a quick check? Run 'headmatch doctor'. Unsure about device names? Run 'headmatch list-targets'.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))


def render_setup_check(ttk, frame, *, report: str, on_refresh, on_measure) -> None:
    ttk.Label(frame, text="Setup check", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Run a quick readiness check before your first measurement. This reuses the same beginner-friendly doctor report as the CLI.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    actions = ttk.Frame(frame)
    actions.grid(row=2, column=0, sticky="w")
    ttk.Button(actions, text="Refresh setup check", command=on_refresh).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Go to Measure", command=on_measure).grid(row=0, column=1, sticky="w", padx=(12, 0))

    # Desktop shortcut button
    from .desktop import shortcut_exists, create_shortcut, find_gui_binary
    gui = find_gui_binary()
    if gui:
        def _toggle_shortcut():
            try:
                if shortcut_exists():
                    from .desktop import remove_shortcut
                    remove_shortcut()
                else:
                    create_shortcut(gui)
            except Exception:
                pass
            on_refresh()
        shortcut_label = "Remove desktop shortcut" if shortcut_exists() else "Create desktop shortcut"
        ttk.Button(actions, text=shortcut_label, command=_toggle_shortcut).grid(row=0, column=2, sticky="w", padx=(12, 0))

    report_card = ttk.LabelFrame(frame, text="Readiness report", padding=SECTION_PAD)
    report_card.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    report_card.columnconfigure(0, weight=1)
    report_card.rowconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)
    try:
        import tkinter as tk
        text_widget = tk.Text(report_card, wrap="word", height=12, relief="flat", bg=report_card.cget("background") if hasattr(report_card, 'cget') else "#ffffff")
        text_widget.insert("1.0", report)
        text_widget.config(state="disabled")
        scrollbar = ttk.Scrollbar(report_card, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    except Exception:
        ttk.Label(report_card, text=report, wraplength=DETAIL_WRAP, justify="left").grid(row=0, column=0, sticky="w")


def render_offline_wizard(ttk, frame, *, variables, on_prepare, on_fit) -> None:
    ttk.Label(frame, text="Offline measurement wizard", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Use this when a handheld recorder is more reliable than live capture. First write the sweep package, then fit the imported WAV.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ttk.LabelFrame(frame, text="What happens", padding=SECTION_PAD)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(OFFLINE_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    prep = ttk.LabelFrame(frame, text="Step A — prepare the recorder package", padding=SECTION_PAD)
    prep.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    prep.columnconfigure(1, weight=1)
    add_picker_row(ttk, prep, 0, "Package folder", variables.output_dir_var, button_text="Browse…", command=variables.choose_output_dir)
    add_entry_row(ttk, prep, 1, "Notes (optional)", variables.offline_notes_var)
    ttk.Button(prep, text="Write sweep package", command=on_prepare).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    fit = ttk.LabelFrame(frame, text="Step B — fit an imported recording", padding=SECTION_PAD)
    fit.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    fit.columnconfigure(1, weight=1)
    add_picker_row(ttk, fit, 0, "Recorded WAV", variables.offline_recording_var, button_text="Browse…", command=variables.choose_offline_recording)
    add_picker_row(ttk, fit, 1, "Fit output folder", variables.offline_fit_output_var, button_text="Browse…", command=variables.choose_offline_fit_output_dir)
    add_picker_row(ttk, fit, 2, "Target CSV (optional)", variables.target_csv_var, button_text="Browse…", command=variables.choose_target_csv)
    add_entry_row(ttk, fit, 3, "Max PEQ filters", variables.max_filters_var)
    ttk.Button(fit, text="Fit imported recording", command=on_fit).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))


def render_progress(ttk, frame, *, title: str, body: str) -> None:
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.LabelFrame(frame, text="What to do now", padding=SECTION_PAD)
    note.grid(row=2, column=0, sticky="ew")
    ttk.Label(
        note,
        text="Keep this window open while the shared pipeline runs. This screen will switch to a completion summary when it finishes.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=0, sticky="w")


def render_completion(ttk, frame, *, title: str, body: str, steps: tuple[str, ...], on_home, on_history) -> None:
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    card = ttk.LabelFrame(frame, text="Next steps", padding=SECTION_PAD)
    card.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(steps):
        ttk.Label(card, text=f"- {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)
    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=3, column=0, sticky="w")
    ttk.Button(actions, text="Back to Measure", command=on_home).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Open Results", command=on_history).grid(row=0, column=1, sticky="w", padx=(12, 0))


def render_history(ttk, frame, *, history_root_var, config_path: Path):
    return build_history_selection(history_root_var.get(), config_path.parent)


_CONFIDENCE_BADGES = {
    'high': '✓',
    'medium': '⚠',
    'low': '✗',
}


def _confidence_display(label: str) -> str:
    return label.replace('_', ' ').title()


def _confidence_badge(label: str) -> str:
    badge = _CONFIDENCE_BADGES.get(label, '')
    return f"{badge} {_confidence_display(label)}" if badge else _confidence_display(label)


def render_history_results(ttk, frame, *, selection) -> None:
    if not selection.items:
        ttk.Label(
            frame,
            text=(
                f"No run_summary.json files were found under {selection.search_root}. "
                "Finish one run with the online or offline wizard, then refresh."
            ),
            wraplength=DETAIL_WRAP,
            justify="left",
        ).grid(row=3, column=0, sticky="w")
        return

    results = ttk.LabelFrame(frame, text="Recent runs", padding=SECTION_PAD)
    results.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    results.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    for idx, entry in enumerate(selection.items):
        confidence = entry.summary.confidence
        ttk.Label(results, text=entry.summary.out_dir, style="Heading.TLabel").grid(row=idx * 3, column=0, sticky="w")
        ttk.Label(
            results,
            text=f"Confidence: {_confidence_badge(confidence.label)} ({confidence.score}/100) — {confidence.headline}",
            wraplength=DETAIL_WRAP,
            justify="left",
        ).grid(row=idx * 3 + 1, column=0, sticky="w")
        ttk.Label(
            results,
            text=f"{entry.summary.kind} | {entry.summary.target} | {entry.summary.sample_rate} Hz",
            wraplength=DETAIL_WRAP,
            justify="left",
        ).grid(row=idx * 3 + 2, column=0, sticky="w", pady=(0, 8))

    next_row = 4
    comparison = selection.comparison
    if comparison is not None:
        compare = ttk.LabelFrame(frame, text="Compare the two most recent runs", padding=SECTION_PAD)
        compare.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        compare.columnconfigure(1, weight=1)
        compare.columnconfigure(2, weight=1)
        ttk.Label(compare, text="Field", style="Heading.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(compare, text=comparison.left_entry.summary.out_dir, style="Heading.TLabel", wraplength=COMPARISON_WRAP, justify="left").grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(compare, text=comparison.right_entry.summary.out_dir, style="Heading.TLabel", wraplength=COMPARISON_WRAP, justify="left").grid(row=0, column=2, sticky="w")
        for idx, field in enumerate(comparison.fields, start=1):
            ttk.Label(compare, text=field.label, style="Heading.TLabel").grid(row=idx, column=0, sticky="nw", padx=(0, 12), pady=(6, 0))
            ttk.Label(compare, text=field.left, wraplength=COMPARISON_WRAP, justify="left").grid(row=idx, column=1, sticky="w", padx=(0, 12), pady=(6, 0))
            ttk.Label(compare, text=field.right, wraplength=COMPARISON_WRAP, justify="left").grid(row=idx, column=2, sticky="w", pady=(6, 0))
        next_row = 5

    guide = ttk.LabelFrame(frame, text="Selected run summary", padding=SECTION_PAD)
    guide.grid(row=next_row, column=0, sticky="ew", pady=(12, 0))
    guide.columnconfigure(0, weight=1)
    summary_text = selection.selected_summary or "No summary selected."
    ttk.Label(guide, text=f"Summary: {summary_text}", wraplength=DETAIL_WRAP, justify="left").grid(row=0, column=0, sticky="w")

    selected = selection.selected_entry
    if selected is not None:
        confidence = selected.summary.confidence
        ttk.Label(
            guide,
            text=f"Confidence: {_confidence_badge(confidence.label)} ({confidence.score}/100)",
            style="Heading.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(guide, text=confidence.headline, wraplength=DETAIL_WRAP, justify="left").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(guide, text=confidence.interpretation, wraplength=DETAIL_WRAP, justify="left").grid(row=3, column=0, sticky="w", pady=(4, 0))
        row = 4
        if confidence.warnings:
            ttk.Label(guide, text="Warnings", style="Heading.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
            row += 1
            for warning in confidence.warnings[:3]:
                ttk.Label(guide, text=f"- {warning}", wraplength=DETAIL_WRAP, justify="left").grid(row=row, column=0, sticky="w", pady=(2, 0))
                row += 1
        steps = confidence_troubleshooting_steps(confidence)
        if steps:
            ttk.Label(guide, text="What to try next", style="Heading.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
            row += 1
            for step in steps:
                ttk.Label(guide, text=f"- {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=row, column=0, sticky="w", pady=(2, 0))
                row += 1
        ttk.Label(guide, text=selection.selected_guide or "", wraplength=DETAIL_WRAP, justify="left").grid(row=row, column=0, sticky="w", pady=(10, 0))
        row += 1
        # TASK-066: Graph display button
        import os
        overview_svg = os.path.join(selected.summary.out_dir, 'fit_overview.svg')
        if os.path.isfile(overview_svg):
            def _open_graph(path=overview_svg):
                try:
                    if sys.platform == 'linux':
                        subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif sys.platform == 'darwin':
                        subprocess.Popen(['open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif sys.platform == 'win32':
                        import os as _os
                        _os.startfile(path)
                except OSError:
                    pass
            ttk.Button(guide, text="Open fit graph", command=_open_graph).grid(row=row, column=0, sticky="w", pady=(8, 0))
        else:
            ttk.Label(guide, text="Graph not available.", wraplength=DETAIL_WRAP, justify="left").grid(row=row, column=0, sticky="w", pady=(8, 0))





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
            canvas.create_line(*coords, fill="#00ccaa", width=2, smooth=True)

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
        _bind_drag_events()

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

    def _on_drag_start(event):
        """Find the closest control point within grab radius."""
        geom = _geom[0]
        if geom is None:
            return
        closest_idx, closest_dist = None, 12  # grab radius in pixels
        for i, point in enumerate(editor.points):
            px = geom.freq_to_x(point.freq_hz)
            py = geom.db_to_y(max(geom.db_min, min(geom.db_max, point.gain_db)))
            dist = ((event.x - px) ** 2 + (event.y - py) ** 2) ** 0.5
            if dist < closest_dist:
                closest_idx, closest_dist = i, dist
        _drag_idx[0] = closest_idx

    def _on_drag_motion(event):
        """Move the dragged control point to cursor position."""
        idx = _drag_idx[0]
        if idx is None:
            return
        geom = _geom[0]
        if geom is None:
            return
        freq = max(20.0, min(20000.0, geom.x_to_freq(event.x)))
        gain = max(-20.0, min(20.0, geom.y_to_db(event.y)))
        editor.move_point(idx, freq, gain)
        # Update matching widgets if they exist
        if idx < len(_vars["freq"]):
            _vars["freq"][idx].set(f"{freq:.0f}")
            _vars["gain"][idx].set(f"{gain:.1f}")
        if idx < len(_vars["gain_labels"]):
            _vars["gain_labels"][idx].config(text=f"{gain:.1f} dB")
        if idx < len(_vars["gain_scales"]):
            try:
                _vars["gain_scales"][idx].set(gain)
            except Exception:
                pass
        _geom[0] = _render_curve_preview(canvas, editor)
        _bind_drag_events()

    def _on_drag_end(_event):
        _drag_idx[0] = None

    def _bind_drag_events():
        """Re-bind drag events after canvas redraw (items get recreated)."""
        canvas.tag_bind("control_point", "<ButtonPress-1>", _on_drag_start)
        canvas.tag_bind("control_point", "<B1-Motion>", _on_drag_motion)
        canvas.tag_bind("control_point", "<ButtonRelease-1>", _on_drag_end)

    _bind_drag_events()

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
            ttk.Button(points_frame, text="\u2715", command=lambda i=idx: _remove_point(i), width=3).grid(
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


# ── Import APO view (extracted from gui.py) ──

def render_import_apo(ttk, frame, *, variables, on_import, on_refine,
                      on_choose_preset, on_choose_output, on_choose_refine_recording,
                      on_choose_refine_target, on_choose_refine_output):
    """Render the Import APO preset view with import + refine sections."""
    ttk.Label(frame, text="Import APO preset", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Load an Equalizer APO parametric preset and re-export it as CamillaDSP and HeadMatch formats.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    form = ttk.LabelFrame(frame, text="Import settings", padding=SECTION_PAD)
    form.grid(row=2, column=0, sticky="ew")
    form.columnconfigure(1, weight=1)
    add_picker_row(ttk, form, 0, "APO preset file", variables.apo_preset_var,
                   button_text="Browse\u2026", command=on_choose_preset)
    add_picker_row(ttk, form, 1, "Output folder", variables.apo_output_dir_var,
                   button_text="Browse\u2026", command=on_choose_output)
    ttk.Button(form, text="Import and convert", command=on_import).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    refine_frame = ttk.LabelFrame(frame, text="Refine against a measurement", padding=SECTION_PAD)
    refine_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    refine_frame.columnconfigure(1, weight=1)
    ttk.Label(
        refine_frame,
        text="Load the same APO preset above, plus a recording WAV, to re-optimise the bands against your actual measurement.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    add_picker_row(ttk, refine_frame, 1, "Recording WAV", variables.apo_refine_recording_var,
                   button_text="Browse\u2026", command=on_choose_refine_recording)
    add_picker_row(ttk, refine_frame, 2, "Target CSV (optional)", variables.apo_refine_target_var,
                   button_text="Browse\u2026", command=on_choose_refine_target)
    add_picker_row(ttk, refine_frame, 3, "Output folder", variables.apo_refine_output_var,
                   button_text="Browse\u2026", command=on_choose_refine_output)
    ttk.Button(refine_frame, text="Refine preset", command=on_refine).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))


# ── Fetch Curve view (extracted from gui.py) ──

def render_fetch_curve(ttk, frame, *, variables, on_search, on_choose_output, on_fetch):
    """Render the Fetch Curve view with search + direct URL sections.

    Returns a dict with 'results_frame' key for the caller to populate search results.
    """
    ttk.Label(frame, text="Fetch published curve", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Search the AutoEQ database for a headphone model, or paste a direct CSV URL.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    search_frame = ttk.LabelFrame(frame, text="Search headphone database", padding=SECTION_PAD)
    search_frame.grid(row=2, column=0, sticky="ew")
    search_frame.columnconfigure(1, weight=1)
    add_entry_row(ttk, search_frame, 0, "Headphone model", variables.fetch_search_var)
    ttk.Button(search_frame, text="Search", command=on_search).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    results_frame = ttk.Frame(frame)
    results_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
    results_frame.columnconfigure(0, weight=1)

    form = ttk.LabelFrame(frame, text="Fetch by URL", padding=SECTION_PAD)
    form.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    form.columnconfigure(1, weight=1)
    add_entry_row(ttk, form, 0, "CSV URL (HTTPS)", variables.fetch_url_var)
    add_picker_row(ttk, form, 1, "Save to", variables.fetch_output_var,
                   button_text="Browse\u2026", command=on_choose_output)
    ttk.Button(form, text="Fetch and save", command=on_fetch).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    return {"results_frame": results_frame}


# ── History page view (extracted from gui.py) ──

def render_history_page(ttk, frame, *, history_root_var, config_path,
                        on_browse, on_refresh):
    """Render the full Results/History page with scrollable results list."""
    import tkinter as tk

    frame.rowconfigure(3, weight=1)
    ttk.Label(frame, text="Results", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Browse recent runs by scanning for run_summary.json files.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    controls = ttk.LabelFrame(frame, text="Search", padding=SECTION_PAD)
    controls.grid(row=2, column=0, sticky="ew")
    controls.columnconfigure(1, weight=1)
    ttk.Label(controls, text="Search folder").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
    ttk.Entry(controls, textvariable=history_root_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))
    ttk.Button(controls, text="Browse\u2026", command=on_browse).grid(row=0, column=2, sticky="e", padx=(8, 0), pady=(0, 8))
    ttk.Button(controls, text="Refresh", command=on_refresh).grid(row=0, column=3, sticky="e", padx=(4, 0), pady=(0, 8))

    scroll_frame = ttk.Frame(frame)
    scroll_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    scroll_frame.columnconfigure(0, weight=1)
    scroll_frame.rowconfigure(0, weight=1)

    canvas = tk.Canvas(scroll_frame, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=scrollbar.set)

    results = ttk.Frame(canvas, padding=(0, 0, 4, 0))
    canvas_window = canvas.create_window((0, 0), window=results, anchor="nw")

    def _sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _fit_width(event):
        canvas.itemconfigure(canvas_window, width=event.width)

    results.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _fit_width)

    selection = render_history(ttk, results, history_root_var=history_root_var, config_path=config_path)
    render_history_results(ttk, results, selection=selection)
    _sync_scroll_region()

