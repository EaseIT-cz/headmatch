"""Tests for headmatch.gui.variables module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from headmatch.gui.state import GuiState


def make_test_state(**overrides) -> GuiState:
    """Create a GuiState with defaults for testing."""
    defaults = {
        "version_display": "1.0.0-test",
        "config_path": Path("/tmp/test_config.yaml"),
        "config_created": False,
        "current_view": "measure-online",
        "mode": "advanced",
        "default_output_dir": "/home/user/HeadMatch/session_01",
        "preferred_target_csv": "/home/user/target.csv",
        "pipewire_output_target": "output_device",
        "pipewire_input_target": "input_device",
        "start_iterations": 3,
        "max_filters": 8,
        "sample_rate": 48000,
        "duration_s": 4.0,
        "f_start_hz": 20.0,
        "f_end_hz": 20000.0,
        "pre_silence_s": 0.3,
        "post_silence_s": 0.05,
        "amplitude": 0.5,
    }
    defaults.update(overrides)
    return GuiState(**defaults)


class DummyVar:
    """Mock tk.StringVar for testing."""
    def __init__(self, master=None, value=""):
        self.master = master
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.fixture
def mock_tk(monkeypatch):
    """Mock tkinter module for testing."""
    mock_tk_mod = SimpleNamespace(StringVar=DummyVar)
    monkeypatch.setitem(sys.modules, 'tkinter', mock_tk_mod)
    return mock_tk_mod


def test_initialize_tkinter_variables_returns_dict(mock_tk):
    """Test that initialize_tkinter_variables returns a dictionary."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state()

    result = initialize_tkinter_variables(root, state)

    assert isinstance(result, dict)


def test_initialize_tkinter_variables_creates_all_expected_vars(mock_tk):
    """Test that all expected variables are created with proper initial values."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state(
        current_view="measure-online",
        mode="advanced",
        default_output_dir="/home/user/HeadMatch/session_01",
        preferred_target_csv="/home/user/target.csv",
        pipewire_output_target="output_device",
        pipewire_input_target="input_device",
        start_iterations=3,
        max_filters=6,
    )

    result = initialize_tkinter_variables(root, state)

    # Check StringVar instances
    assert result["current_view"].get() == "measure-online"
    assert result["mode_var"].get() == "advanced"
    assert result["output_dir_var"].get() == "/home/user/HeadMatch/session_01"
    assert result["target_csv_var"].get() == "/home/user/target.csv"
    assert result["output_target_var"].get() == "output_device"
    assert result["input_target_var"].get() == "input_device"
    assert result["iterations_var"].get() == "3"
    assert result["iteration_mode_var"].get() == "independent"
    assert result["max_filters_var"].get() == "6"


def test_initialize_tkinter_variables_creates_default_paths(mock_tk):
    """Test that default paths are derived correctly from state."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state(default_output_dir="~/HeadMatch/session_01")

    result = initialize_tkinter_variables(root, state)

    # Check paths are expanded and derived correctly
    expanded_dir = str(Path("~/HeadMatch/session_01").expanduser())
    parent_dir = str(Path(expanded_dir).parent)

    assert result["history_root_var"].get() == parent_dir
    assert result["offline_fit_output_var"].get() == str(Path(expanded_dir) / "fit")
    assert result["apo_output_dir_var"].get() == str(Path(expanded_dir) / "imported")
    assert result["apo_refine_output_var"].get() == str(Path(expanded_dir) / "refined")


def test_initialize_tkinter_variables_creates_empty_default_vars(mock_tk):
    """Test that optional variables default to empty strings."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state()

    result = initialize_tkinter_variables(root, state)

    # Check empty defaults
    assert result["offline_recording_var"].get() == ""
    assert result["offline_notes_var"].get() == ""
    assert result["apo_preset_var"].get() == ""
    assert result["apo_refine_recording_var"].get() == ""
    assert result["apo_refine_target_var"].get() == ""
    assert result["fetch_url_var"].get() == ""
    assert result["fetch_output_var"].get() == ""
    assert result["fetch_search_var"].get() == ""
    assert result["target_editor_save_path_var"].get() == ""
    assert result["basic_search_query_var"].get() == ""
    assert result["basic_search_results_var"].get() == ""
    assert result["basic_search_choice_var"].get() == ""
    assert result["basic_target_path_var"].get() == ""
    assert result["basic_clone_source_var"].get() == ""
    assert result["basic_clone_target_var"].get() == ""
    assert result["basic_clone_output_var"].get() == ""


def test_initialize_tkinter_variables_creates_basic_mode_vars(mock_tk):
    """Test that basic mode variables are created with correct defaults."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state(
        current_view="basic-mode",
        mode="basic",
        preferred_target_csv="/custom/target.csv",
    )

    result = initialize_tkinter_variables(root, state)

    assert result["basic_step_var"].get() == "target"
    assert result["basic_target_mode_var"].get() == "flat"
    assert result["basic_target_csv_var"].get() == "/custom/target.csv"


def test_initialize_tkinter_variables_creates_progress_vars(mock_tk):
    """Test that progress and completion variables are created."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state()

    result = initialize_tkinter_variables(root, state)

    assert result["basic_progress_var"].get() == ""
    assert result["progress_title_var"].get() == ""
    assert result["progress_body_var"].get() == ""
    assert result["completion_title_var"].get() == ""
    assert result["completion_body_var"].get() == ""
    assert result["doctor_report_var"].get() == ""


def test_initialize_tkinter_variables_creates_hearing_vars(mock_tk):
    """Test that hearing test variables are created with correct defaults."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state()

    result = initialize_tkinter_variables(root, state)

    assert result["hearing_profile"] is None
    assert result["_force_new_hearing_test"] is False
    assert result["hearing_target_var"].get() == "Flat (default)"
    assert result["hearing_flatten_var"].get() == "Off — compensate to normal"


def test_initialize_tkinter_variables_creates_target_options(mock_tk):
    """Test that target options are created as tuples."""
    from headmatch.gui.variables import initialize_tkinter_variables

    root = SimpleNamespace()
    state = make_test_state()

    result = initialize_tkinter_variables(root, state)

    assert result["output_target_options"] == ()
    assert result["input_target_options"] == ()
    assert isinstance(result["basic_search_matches"], list)
    assert result["basic_search_matches"] == []
    assert result["content"] is None