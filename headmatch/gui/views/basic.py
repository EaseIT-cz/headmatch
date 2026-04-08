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
        ttk.Label(card, text="Target source").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=3)
        combo = ttk.Combobox(card, textvariable=variables.basic_target_mode_var, values=("flat", "csv", "database"), state="readonly")
        combo.grid(row=0, column=1, sticky="ew", pady=3)
        if hasattr(combo, 'bind') and hasattr(variables, 'refresh_basic_mode_target_step'):
            combo.bind("<<ComboboxSelected>>", lambda _evt: variables.refresh_basic_mode_target_step())
        target_mode = (variables.basic_target_mode_var.get().strip() or 'flat')
        row = 1
        if target_mode == 'csv':
            add_picker_row(ttk, card, row, "Target CSV", variables.basic_target_csv_var, button_text="Browse…", command=variables.choose_target_csv)
            row += 1
        elif target_mode == 'database':
            add_entry_row(ttk, card, row, "Search database", variables.basic_search_query_var)
            ttk.Button(card, text="Search", command=on_search).grid(row=row + 1, column=0, sticky="w", pady=(6, 0))
            ttk.Label(card, textvariable=variables.basic_search_results_var, wraplength=DETAIL_WRAP, justify="left").grid(row=row + 1, column=1, sticky="w", pady=(6, 0))
            row += 2
            matches = list(getattr(variables, "basic_search_matches", []) or [])
            if len(matches) > 1:
                ttk.Label(card, text="Choose a measurement", style="Heading.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
                row += 1
                for idx, entry in enumerate(matches):
                    label = f"{entry.name} — {entry.source} ({entry.form_factor})"
                    ttk.Button(card, text=label, command=lambda i=idx: variables.choose_basic_search_match(i)).grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
                    row += 1
            elif getattr(variables, "basic_search_choice_var", None) is not None and variables.basic_search_choice_var.get().strip():
                ttk.Label(card, text=f"Selected: {variables.basic_search_choice_var.get()}", wraplength=DETAIL_WRAP, justify="left").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
                row += 1
        ttk.Button(card, text="Next: Measurement", command=on_next).grid(row=row, column=0, sticky="w", pady=(10, 0))
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
