from __future__ import annotations

import sys

from .common import BODY_WRAP, DETAIL_WRAP, SECTION_PAD


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
    from ...desktop import shortcut_exists, create_shortcut, find_gui_binary
    gui = find_gui_binary() if sys.platform == "linux" else None
    if gui:
        def _toggle_shortcut():
            try:
                if shortcut_exists():
                    from ...desktop import remove_shortcut
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


__all__ = ['render_setup_check']
