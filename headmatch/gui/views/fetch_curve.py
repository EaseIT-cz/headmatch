from __future__ import annotations

from .common import BODY_WRAP, SECTION_PAD, add_entry_row, add_picker_row


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


__all__ = ['render_fetch_curve']
