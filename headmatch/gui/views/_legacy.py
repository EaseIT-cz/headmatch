from __future__ import annotations

from pathlib import Path

from ...history import build_history_selection
import subprocess
import sys
from ...troubleshooting import confidence_troubleshooting_steps


ONLINE_STEPS = (
    "Check the output folder and saved audio device targets.",
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


CLONE_TARGET_STEPS = (
    "Pick the source sweep recording measurement artifact you want to clone from.",
    "Pick the target sweep recording measurement artifact you want to match.",
    "Write the clone target CSV and reuse it in the measurement/fitting workflow.",
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
    import sys
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


def render_completion(ttk, frame, *, title: str, body: str, steps: tuple[str, ...], clipping_assessment=None, on_home, on_history) -> None:
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    row = 2
    if clipping_assessment:
        card = ttk.LabelFrame(frame, text="EQ clipping assessment", padding=SECTION_PAD)
        card.grid(row=row, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        indicator = "⚠" if clipping_assessment.get("will_clip") else "✓"
        status = "Clipping risk detected" if clipping_assessment.get("will_clip") else "No clipping risk detected"
        ttk.Label(card, text=f"{indicator} {status}", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Preamp recommendation").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{float(clipping_assessment.get('preamp_db', 0.0)):+.2f} dB").grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(card, text="Max boost level").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{max(float(clipping_assessment.get('left_peak_boost_db', 0.0)), float(clipping_assessment.get('right_peak_boost_db', 0.0))):+.2f} dB").grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(card, text="Headroom loss").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{float(clipping_assessment.get('headroom_loss_db', 0.0)):.2f} dB").grid(row=3, column=1, sticky="w", pady=2)
        warning = clipping_assessment.get("quality_concern")
        if warning:
            ttk.Label(card, text="Quality warning").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=2)
            ttk.Label(card, text=warning, wraplength=DETAIL_WRAP, justify="left").grid(row=4, column=1, sticky="w", pady=2)
        row += 1
    card = ttk.LabelFrame(frame, text="Next steps", padding=SECTION_PAD)
    card.grid(row=row, column=0, sticky="ew")
    for idx, step in enumerate(steps):
        ttk.Label(card, text=f"- {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)
    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=row + 1, column=0, sticky="w")
    ttk.Button(actions, text="Back to Measure", command=on_home).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Open Results", command=on_history).grid(row=0, column=1, sticky="w", padx=(12, 0))



def render_basic_mode(ttk, frame, *, variables, on_next, on_back, on_measure, on_export, on_search) -> None:
    ttk.Label(frame, text="Basic Mode", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text="A simple 3-step wizard with safe defaults. Advanced controls stay hidden.", wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ("Target selection", "Measurement", "Review & Export")
    step_frame = ttk.LabelFrame(frame, text="Wizard steps", padding=SECTION_PAD)
    step_frame.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(steps):
        ttk.Label(step_frame, text=f"{idx + 1}. {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    current = variables.basic_step_var.get()
    card = ttk.LabelFrame(frame, text=f"Step { {'target': '1', 'measure': '2', 'review': '3'}.get(current, '1')} — { {'target': 'Target selection', 'measure': 'Measurement', 'review': 'Review & Export'}.get(current, 'Target selection')}", padding=SECTION_PAD)
    card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    card.columnconfigure(1, weight=1)

    if current == 'target':
        add_combobox_row(ttk, card, 0, "Target source", variables.basic_target_mode_var, ("flat", "csv", "database"), empty_label="")
        add_picker_row(ttk, card, 1, "Target CSV", variables.basic_target_csv_var, button_text="Browse…", command=variables.choose_target_csv)
        add_entry_row(ttk, card, 2, "Search database", variables.basic_search_query_var)
        ttk.Button(card, text="Search", command=on_search).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(card, textvariable=variables.basic_search_results_var, wraplength=DETAIL_WRAP, justify="left").grid(row=3, column=1, sticky="w", pady=(6, 0))
        ttk.Button(card, text="Next: Measurement", command=on_next).grid(row=4, column=0, sticky="w", pady=(10, 0))
    elif current == 'measure':
        ttk.Label(card, text="Safe defaults: sample rate 48000 Hz, 3 iterations averaged, default playback/capture devices, max 10 PEQ filters.", wraplength=DETAIL_WRAP, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, textvariable=variables.basic_progress_var, wraplength=DETAIL_WRAP, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(card, text="Start Measurement", command=on_measure).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(card, text="Back", command=on_back).grid(row=2, column=1, sticky="w", pady=(8, 0))
    else:
        ttk.Label(card, text="Review the result and export to the default location.", wraplength=DETAIL_WRAP, justify="left").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Max PEQ filters: 10", style="Heading.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(card, textvariable=variables.basic_export_path_var, wraplength=DETAIL_WRAP, justify="left").grid(row=2, column=0, sticky="w")
        ttk.Button(card, text="Export", command=on_export).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(card, text="Back", command=on_back).grid(row=3, column=1, sticky="w", pady=(8, 0))


def render_clone_target_workflow(ttk, frame, *, variables, on_create, on_back) -> None:
    ttk.Label(frame, text="Clone Target", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text="Create a relative target curve from two sweep recording measurement artifacts. This is the basic-mode path for headphone cloning and mic coloration nulling.",
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))
    steps = ttk.LabelFrame(frame, text="What happens", padding=SECTION_PAD)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(CLONE_TARGET_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

    form = ttk.LabelFrame(frame, text="Inputs", padding=SECTION_PAD)
    form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    form.columnconfigure(1, weight=1)
    add_picker_row(ttk, form, 0, "Source measurement CSV", variables.basic_clone_source_var, button_text="Browse…", command=variables.choose_basic_clone_source)
    add_picker_row(ttk, form, 1, "Target measurement CSV", variables.basic_clone_target_var, button_text="Browse…", command=variables.choose_basic_clone_target)
    add_picker_row(ttk, form, 2, "Output clone target CSV", variables.basic_clone_output_var, button_text="Browse…", command=variables.choose_basic_clone_output)

    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=4, column=0, sticky="w")
    ttk.Button(actions, text="Create clone target", command=on_create).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Back to Basic Mode", command=on_back).grid(row=0, column=1, sticky="w", padx=(12, 0))


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

