"""Tkinter variable initialization for HeadMatch GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import GuiState


def initialize_tkinter_variables(root, state: GuiState) -> dict[str, Any]:
    """Initialize all Tkinter StringVar and state variables for the GUI app.

    Returns a dictionary mapping variable names to their tk.StringVar instances
    and other state attributes.
    """
    import tkinter as tk

    variables: dict[str, Any] = {}

    variables["current_view"] = tk.StringVar(master=root, value=state.current_view)
    variables["mode_var"] = tk.StringVar(master=root, value=state.mode)
    variables["output_dir_var"] = tk.StringVar(master=root, value=state.default_output_dir)
    variables["target_csv_var"] = tk.StringVar(master=root, value=state.preferred_target_csv)
    variables["output_target_var"] = tk.StringVar(master=root, value=state.pipewire_output_target)
    variables["input_target_var"] = tk.StringVar(master=root, value=state.pipewire_input_target)
    variables["output_target_options"] = ()
    variables["input_target_options"] = ()
    variables["iterations_var"] = tk.StringVar(master=root, value=str(state.start_iterations))
    variables["iteration_mode_var"] = tk.StringVar(master=root, value="independent")
    variables["max_filters_var"] = tk.StringVar(master=root, value=str(state.max_filters))
    variables["history_root_var"] = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser().parent))
    variables["offline_recording_var"] = tk.StringVar(master=root, value="")
    variables["offline_fit_output_var"] = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "fit"))
    variables["offline_notes_var"] = tk.StringVar(master=root, value="")
    variables["apo_preset_var"] = tk.StringVar(master=root, value="")
    variables["apo_output_dir_var"] = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "imported"))
    variables["apo_refine_recording_var"] = tk.StringVar(master=root, value="")
    variables["apo_refine_target_var"] = tk.StringVar(master=root, value="")
    variables["apo_refine_output_var"] = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "refined"))
    variables["fetch_url_var"] = tk.StringVar(master=root, value="")
    variables["fetch_output_var"] = tk.StringVar(master=root, value="")
    variables["fetch_search_var"] = tk.StringVar(master=root, value="")
    variables["target_editor_save_path_var"] = tk.StringVar(master=root, value="")
    variables["basic_step_var"] = tk.StringVar(master=root, value="target")
    variables["basic_target_mode_var"] = tk.StringVar(master=root, value="flat")
    variables["basic_search_query_var"] = tk.StringVar(master=root, value="")
    variables["basic_search_results_var"] = tk.StringVar(master=root, value="")
    variables["basic_search_choice_var"] = tk.StringVar(master=root, value="")
    variables["basic_search_matches"] = []
    variables["basic_target_csv_var"] = tk.StringVar(master=root, value=state.preferred_target_csv)
    variables["basic_target_path_var"] = tk.StringVar(master=root, value="")
    variables["basic_clone_source_var"] = tk.StringVar(master=root, value="")
    variables["basic_clone_target_var"] = tk.StringVar(master=root, value="")
    variables["basic_clone_output_var"] = tk.StringVar(master=root, value="")
    variables["hearing_profile"] = None  # HearingProfile | None; set after a successful test
    variables["_force_new_hearing_test"] = False  # skip the saved-profile landing once
    variables["hearing_target_var"] = tk.StringVar(master=root, value="Flat (default)")  # advanced-mode tonal target
    variables["hearing_flatten_var"] = tk.StringVar(master=root, value="Off — compensate to normal")  # advanced-mode flatten knob
    variables["basic_progress_var"] = tk.StringVar(master=root, value="")
    variables["progress_title_var"] = tk.StringVar(master=root, value="")
    variables["progress_body_var"] = tk.StringVar(master=root, value="")
    variables["completion_title_var"] = tk.StringVar(master=root, value="")
    variables["completion_body_var"] = tk.StringVar(master=root, value="")
    variables["doctor_report_var"] = tk.StringVar(master=root, value="")
    variables["content"] = None

    return variables
