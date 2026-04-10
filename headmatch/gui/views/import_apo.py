from __future__ import annotations

from .common import BODY_WRAP, SECTION_PAD, add_picker_row


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
        wraplength=520,
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


__all__ = ['render_import_apo']
