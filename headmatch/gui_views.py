from __future__ import annotations

from pathlib import Path

from .history import build_history_selection
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
    state = "readonly" if values else "disabled"
    combo = ttk.Combobox(parent, textvariable=variable, values=values, state=state)
    combo.grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)
    if not values:
        variable.set("")
        combo.set(empty_label)


def add_entry_row(ttk, parent, row: int, label: str, variable) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=FIELD_PAD_Y)
    ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=FIELD_PAD_Y)


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
    add_entry_row(ttk, form, 0, "Output folder", variables.output_dir_var)
    add_combobox_row(ttk, form, 1, "Playback target", variables.output_target_var, variables.output_target_options, empty_label="No playback targets found")
    add_combobox_row(ttk, form, 2, "Capture target", variables.input_target_var, variables.input_target_options, empty_label="No capture targets found")
    add_entry_row(ttk, form, 3, "Target CSV (optional)", variables.target_csv_var)
    add_entry_row(ttk, form, 4, "Iterations", variables.iterations_var)
    add_entry_row(ttk, form, 5, "Max PEQ filters", variables.max_filters_var)

    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=4, column=0, sticky="w")
    ttk.Button(actions, text="Start guided measurement", command=on_start).grid(row=0, column=0, sticky="w")
    ttk.Label(
        actions,
        text="Rig ready and room quiet. Need a quick check? Run 'headmatch doctor'. Unsure about device names? Run 'headmatch list-targets'.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))


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
    add_entry_row(ttk, prep, 0, "Package folder", variables.output_dir_var)
    add_entry_row(ttk, prep, 1, "Notes (optional)", variables.offline_notes_var)
    ttk.Button(prep, text="Write sweep package", command=on_prepare).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    fit = ttk.LabelFrame(frame, text="Step B — fit an imported recording", padding=SECTION_PAD)
    fit.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    fit.columnconfigure(1, weight=1)
    add_entry_row(ttk, fit, 0, "Recorded WAV", variables.offline_recording_var)
    add_entry_row(ttk, fit, 1, "Fit output folder", variables.offline_fit_output_var)
    add_entry_row(ttk, fit, 2, "Target CSV (optional)", variables.target_csv_var)
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


def _confidence_display(label: str) -> str:
    return label.replace('_', ' ').title()


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
            text=f"Confidence: {_confidence_display(confidence.label)} ({confidence.score}/100) — {confidence.headline}",
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
            text=f"Confidence: {_confidence_display(confidence.label)} ({confidence.score}/100)",
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
