from __future__ import annotations

from .common import BODY_WRAP, CLONE_TARGET_STEPS, DETAIL_WRAP, SECTION_PAD, add_combobox_row, add_entry_row, add_picker_row


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
    ttk.Label(frame, text="Create a relative target curve from two sweep recording measurement artifacts. This is the basic-mode path for headphone cloning and mic coloration nulling.", wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
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
