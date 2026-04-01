from __future__ import annotations

from pathlib import Path

import pytest

from headmatch.contracts import FrontendConfig
from headmatch.gui import NAV_ITEMS, build_arg_parser, load_gui_state, main



def test_load_gui_state_preloads_saved_config_values(tmp_path):
    config = FrontendConfig(
        default_output_dir="saved/session",
        preferred_target_csv="targets/custom.csv",
        pipewire_output_target="speakers",
        pipewire_input_target="in-ear-mic",
        start_iterations=3,
        max_filters=6,
    )

    state = load_gui_state(config_loader=lambda _path=None: (config, tmp_path / "config.json", False))

    assert state.version_display == "0.2.0"
    assert state.current_view == "home"
    assert state.default_output_dir == "saved/session"
    assert state.preferred_target_csv == "targets/custom.csv"
    assert state.pipewire_output_target == "speakers"
    assert state.pipewire_input_target == "in-ear-mic"
    assert state.start_iterations == 3
    assert state.max_filters == 6



def test_load_gui_state_uses_safe_defaults_when_config_is_empty(tmp_path):
    state = load_gui_state(config_loader=lambda _path=None: (FrontendConfig(), tmp_path / "config.json", True))

    assert state.default_output_dir == "out/session_01"
    assert state.preferred_target_csv == ""
    assert state.pipewire_output_target == ""
    assert state.pipewire_input_target == ""
    assert state.config_created is True



def test_navigation_items_cover_shell_sections():
    assert [item.key for item in NAV_ITEMS] == [
        "home",
        "measure-online",
        "prepare-offline",
        "history",
    ]



def test_gui_main_reports_tcl_startup_errors(monkeypatch):
    monkeypatch.setattr("headmatch.gui.create_app", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        main([])

    class FakeTclError(Exception):
        pass

    FakeTclError.__name__ = "TclError"
    monkeypatch.setattr("headmatch.gui.create_app", lambda **_kwargs: (_ for _ in ()).throw(FakeTclError("no display")))

    with pytest.raises(SystemExit) as exc:
        main([])

    assert str(exc.value) == "GUI could not start: no display"



def test_gui_arg_parser_accepts_config_override():
    parser = build_arg_parser()
    args = parser.parse_args(["--config", str(Path("custom.json"))])
    assert args.config == "custom.json"


def test_gui_history_selection_reads_recent_runs(tmp_path):
    run_dir = tmp_path / "session_01"
    run_dir.mkdir()
    guide = run_dir / "README.txt"
    guide.write_text("headmatch fit results\n")
    summary = run_dir / "run_summary.json"
    summary.write_text(
        """{
  "kind": "fit",
  "out_dir": "%s",
  "sample_rate": 48000,
  "frequency_points": 512,
  "target": "flat",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.0, "right_rms": 1.1, "left_max": 3.0, "right_max": 3.1},
  "results_guide": "%s"
}
""" % (run_dir, guide)
    )

    state = load_gui_state(config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / "out" / "session_01")), tmp_path / "config.json", False))
    app = object.__new__(__import__("headmatch.gui", fromlist=["HeadMatchGuiApp"]).HeadMatchGuiApp)
    app.state = state

    class DummyVar:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    app.history_root_var = DummyVar(str(tmp_path))

    selection = app.build_history_selection()

    assert selection.search_root == str(tmp_path)
    assert selection.selected_summary == str(summary)
    assert "headmatch fit results" in selection.selected_guide
    assert selection.items[0][0] == str(run_dir)
