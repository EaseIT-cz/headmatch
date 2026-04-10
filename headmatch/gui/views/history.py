from __future__ import annotations

import os
import subprocess
import sys

from pathlib import Path

from .common import (
    BODY_WRAP,
    DETAIL_WRAP,
    COMPARISON_WRAP,
    SECTION_PAD,
    _confidence_badge,
    render_history,
)


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
        from ...troubleshooting import confidence_troubleshooting_steps
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


__all__ = ['render_history_page', 'render_history_results']
