from __future__ import annotations

from .common import (
    add_readonly_row,
    add_combobox_row,
    add_entry_row,
    add_picker_row,
    SECTION_PAD,
    FIELD_PAD_Y,
    BODY_WRAP,
    DETAIL_WRAP,
    COMPARISON_WRAP,
    ONLINE_STEPS,
    OFFLINE_STEPS,
    CLONE_TARGET_STEPS,
)
from .completion import render_progress, render_completion
from .online import render_online_wizard
from .setup import render_setup_check
from .offline import render_offline_wizard
from .basic import render_basic_mode, render_clone_target_workflow
from .history import (
    render_history_page,
    render_history_results,
    render_history,
    _confidence_badge,
    _confidence_display,
)
from .target_editor import (
    render_target_editor,
    _PlotGeometry,
    _plot_geometry,
    _render_curve_preview,
)


# Note: render_online_wizard is now implemented in .online and re-exported here for backward compatibility
# Note: render_setup_check is now implemented in .setup and re-exported here for backward compatibility
# Note: render_offline_wizard is now implemented in .offline and re-exported here for backward compatibility
# Note: render_progress and render_completion are now implemented in .completion and re-exported here for backward compatibility
# Note: render_basic_mode and render_clone_target_workflow are now implemented in .basic and re-exported here for backward compatibility
# Note: render_history_page, render_history_results, render_history are now implemented in .history and re-exported here for backward compatibility
# Note: render_target_editor, _PlotGeometry, _plot_geometry, _render_curve_preview are now implemented in .target_editor and re-exported here for backward compatibility


# Re-export basic mode views
__all__ = [
    'render_basic_mode',
    'render_clone_target_workflow',
]


# TOKEN_WARNING_CLASS = "Warning.TLabel" # Removed in TASK-089a

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


# Note: render_history_page, render_history_results, render_history are now implemented in .history and re-exported here for backward compatibility