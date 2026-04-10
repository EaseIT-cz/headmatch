from __future__ import annotations

from .common import (
    BODY_WRAP,
    DETAIL_WRAP,
    SECTION_PAD,
    ONLINE_STEPS,
    add_combobox_row,
    add_entry_row,
    add_picker_row,
)


def render_online_wizard(ttk, frame, *, variables, on_start) -> None:
    ttk.Label(frame, text="Online measurement wizard", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Use this when audio playback and capture are available now. Choose the output that should play the sweep and the input that should hear it.",
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

    # Show explicit guidance when device lists are empty
    has_playback = bool(variables.output_target_options)
    has_capture = bool(variables.input_target_options)
    if not has_playback or not has_capture:
        help_frame = ttk.LabelFrame(frame, text="\u26A0 Device setup help", padding=SECTION_PAD)
        help_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        missing_parts = []
        if not has_playback:
            missing_parts.append("playback")
        if not has_capture:
            missing_parts.append("capture")
        missing_text = " and ".join(missing_parts)
        ttk.Label(
            help_frame,
            text=(
                f"No {missing_text} devices were discovered. This usually means PipeWire is not running "
                "or the audio hardware is disconnected. Try these steps:"
            ),
            wraplength=DETAIL_WRAP, justify="left",
        ).grid(row=0, column=0, sticky="w")
        for i, step in enumerate([
            "1. Check that your audio interface/DAC is connected and powered on.",
            "2. Run 'headmatch doctor' in a terminal to diagnose the issue.",
            "3. Run 'headmatch list-targets' to see what PipeWire can find.",
            "4. If you know the device name, type it directly into the field above.",
        ], start=1):
            ttk.Label(help_frame, text=step, wraplength=DETAIL_WRAP, justify="left").grid(
                row=i, column=0, sticky="w", pady=2,
            )
        action_row = 5
    else:
        action_row = 4

    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=action_row + 1, column=0, sticky="w")
    ttk.Button(actions, text="Start guided measurement", command=on_start).grid(row=0, column=0, sticky="w")
    ttk.Label(
        actions,
        text="Rig ready and room quiet. Need a quick check? Run 'headmatch doctor'. Unsure about device names? Run 'headmatch list-targets'.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))


__all__ = ['render_online_wizard']
