from __future__ import annotations

from pathlib import Path

from ...history import build_history_selection

SECTION_PAD = 12
FIELD_PAD_Y = 3
BODY_WRAP = 560
DETAIL_WRAP = 520
COMPARISON_WRAP = 240

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


def render_history(ttk, frame, *, history_root_var, config_path: Path):
    return build_history_selection(history_root_var.get(), config_path.parent)


_CONFIDENCE_BADGES = {'high': '✓', 'medium': '⚠', 'low': '✗'}


def _confidence_display(label: str) -> str:
    return label.replace('_', ' ').title()


def _confidence_badge(label: str) -> str:
    badge = _CONFIDENCE_BADGES.get(label, '')
    return f"{badge} {_confidence_display(label)}" if badge else _confidence_display(label)
