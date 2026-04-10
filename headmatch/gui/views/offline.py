from __future__ import annotations

from .common import (
    BODY_WRAP,
    DETAIL_WRAP,
    SECTION_PAD,
    OFFLINE_STEPS,
    add_entry_row,
    add_picker_row,
)


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


__all__ = ['render_offline_wizard']
