from __future__ import annotations

from pathlib import Path

from .history import build_history_selection


ONLINE_STEPS = (
    "Check the output folder and saved PipeWire targets.",
    "Press Start when your measurement rig is ready.",
    "HeadMatch will run the shared online pipeline and then show the output folder.",
)


OFFLINE_STEPS = (
    "Prepare a sweep package if you need to record with a handheld recorder first.",
    "After recording, point the GUI at the WAV file and run the offline fit.",
    "Both actions reuse the same shared sweep and fitting pipeline as the CLI and TUI.",
)


def add_readonly_row(ttk, parent, row: int, label: str, variable) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
    entry = ttk.Entry(parent, textvariable=variable)
    entry.state(["readonly"])
    entry.grid(row=row, column=1, sticky="ew", pady=4)


def add_entry_row(ttk, parent, row: int, label: str, variable) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
    ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)


def render_home(ttk, frame, *, state, variables) -> None:
    ttk.Label(frame, text="Main screen", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text=(
            "Choose the online path if PipeWire playback/capture is working today, or the offline path if you want to "
            "record first and import the WAV later. The saved defaults below preload both workflows."
        ),
        wraplength=620,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 16))
    card = ttk.LabelFrame(frame, text="Saved defaults", padding=16)
    card.grid(row=2, column=0, sticky="ew")
    card.columnconfigure(1, weight=1)
    add_readonly_row(ttk, card, 0, "Output folder", variables.output_dir_var)
    add_readonly_row(ttk, card, 1, "Playback target", variables.output_target_var)
    add_readonly_row(ttk, card, 2, "Capture target", variables.input_target_var)
    add_readonly_row(ttk, card, 3, "Target CSV", variables.target_csv_var)
    add_readonly_row(ttk, card, 4, "Iterations", variables.iterations_var)
    add_readonly_row(ttk, card, 5, "Max PEQ filters", variables.max_filters_var)
    note = f"Config file: {state.config_path}"
    if state.config_created:
        note += " (created with starter defaults on this launch)"
    ttk.Label(frame, text=note, wraplength=620, justify="left").grid(row=3, column=0, sticky="w", pady=(12, 0))


def render_online_wizard(ttk, frame, *, variables, on_start) -> None:
    ttk.Label(frame, text="Online measurement wizard", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Use this when PipeWire playback and capture are available now. The GUI keeps the first run simple and uses the shared measure → analyze → fit pipeline.",
        wraplength=650,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ttk.LabelFrame(frame, text="What happens", padding=16)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(ONLINE_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    form = ttk.LabelFrame(frame, text="Run details", padding=16)
    form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    form.columnconfigure(1, weight=1)
    add_entry_row(ttk, form, 0, "Output folder", variables.output_dir_var)
    add_entry_row(ttk, form, 1, "Playback target", variables.output_target_var)
    add_entry_row(ttk, form, 2, "Capture target", variables.input_target_var)
    add_entry_row(ttk, form, 3, "Target CSV (optional)", variables.target_csv_var)
    add_entry_row(ttk, form, 4, "Iterations", variables.iterations_var)
    add_entry_row(ttk, form, 5, "Max PEQ filters", variables.max_filters_var)

    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=4, column=0, sticky="w")
    ttk.Button(actions, text="Start guided measurement", command=on_start).grid(row=0, column=0, sticky="w")
    ttk.Label(actions, text="Make sure your headphone rig is connected and quiet before you start.").grid(
        row=0, column=1, sticky="w", padx=(12, 0)
    )


def render_offline_wizard(ttk, frame, *, variables, on_prepare, on_fit) -> None:
    ttk.Label(frame, text="Offline measurement wizard", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Use this when a handheld recorder is more reliable than live capture. First prepare the sweep package, then come back and fit the imported WAV.",
        wraplength=650,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ttk.LabelFrame(frame, text="What happens", padding=16)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(OFFLINE_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    prep = ttk.LabelFrame(frame, text="Step A — prepare the recorder package", padding=16)
    prep.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    prep.columnconfigure(1, weight=1)
    add_entry_row(ttk, prep, 0, "Package folder", variables.output_dir_var)
    add_entry_row(ttk, prep, 1, "Notes (optional)", variables.offline_notes_var)
    ttk.Button(prep, text="Write sweep package", command=on_prepare).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    fit = ttk.LabelFrame(frame, text="Step B — fit an imported recording", padding=16)
    fit.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    fit.columnconfigure(1, weight=1)
    add_entry_row(ttk, fit, 0, "Recorded WAV", variables.offline_recording_var)
    add_entry_row(ttk, fit, 1, "Fit output folder", variables.offline_fit_output_var)
    add_entry_row(ttk, fit, 2, "Target CSV (optional)", variables.target_csv_var)
    add_entry_row(ttk, fit, 3, "Max PEQ filters", variables.max_filters_var)
    ttk.Button(fit, text="Fit imported recording", command=on_fit).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))


def render_progress(ttk, frame, *, title: str, body: str) -> None:
    ttk.Label(frame, text=title, font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=650, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.LabelFrame(frame, text="What to do now", padding=16)
    note.grid(row=2, column=0, sticky="ew")
    ttk.Label(
        note,
        text="Keep this window open while the shared pipeline runs. When the task finishes, this screen will switch to a completion summary automatically.",
        wraplength=620,
        justify="left",
    ).grid(row=0, column=0, sticky="w")


def render_completion(ttk, frame, *, title: str, body: str, steps: tuple[str, ...], on_home, on_history) -> None:
    ttk.Label(frame, text=title, font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=650, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    card = ttk.LabelFrame(frame, text="Next steps", padding=16)
    card.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(steps):
        ttk.Label(card, text=f"- {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)
    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=3, column=0, sticky="w")
    ttk.Button(actions, text="Back to Home", command=on_home).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Open History", command=on_history).grid(row=0, column=1, sticky="w", padx=(12, 0))


def render_history(ttk, frame, *, history_root_var, config_path: Path):
    return build_history_selection(history_root_var.get(), config_path.parent)


def render_history_results(ttk, frame, *, selection) -> None:
    if not selection.items:
        ttk.Label(
            frame,
            text=(
                f"No run_summary.json files were found under {selection.search_root}. "
                "Finish one run with the online or offline wizard, then refresh."
            ),
            wraplength=620,
            justify="left",
        ).grid(row=3, column=0, sticky="w")
        return

    results = ttk.LabelFrame(frame, text="Recent runs", padding=16)
    results.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
    results.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    for idx, (_folder, label, details) in enumerate(selection.items):
        ttk.Label(results, text=label, font=("TkDefaultFont", 10, "bold")).grid(row=idx * 2, column=0, sticky="w")
        ttk.Label(results, text=details, wraplength=620, justify="left").grid(row=idx * 2 + 1, column=0, sticky="w", pady=(0, 8))

    guide = ttk.LabelFrame(frame, text="Selected guide", padding=16)
    guide.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    guide.columnconfigure(0, weight=1)
    summary_text = selection.selected_summary or "No summary selected."
    ttk.Label(guide, text=f"Summary: {summary_text}", wraplength=620, justify="left").grid(row=0, column=0, sticky="w")
    ttk.Label(guide, text=selection.selected_guide or "", wraplength=620, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 0))
