from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from headmatch.gui.shell import HeadMatchGuiApp, NavigationItem
from headmatch.headphone_db import HeadphoneEntry
from tests.test_gui import DummyVar


def test_resolve_device_display_prefers_labeled_option():
    options = ("12 — USB DAC", "13 — Mic")
    assert HeadMatchGuiApp._resolve_device_display("12", options) == "12 — USB DAC"
    assert HeadMatchGuiApp._resolve_device_display("99", options) == "99"


def test_strip_device_label_returns_bare_id():
    assert HeadMatchGuiApp._strip_device_label("12 — USB DAC") == "12"
    assert HeadMatchGuiApp._strip_device_label("plain") == "plain"


def test_parse_positive_int_validates_input():
    app = SimpleNamespace()
    assert HeadMatchGuiApp._parse_positive_int(app, "3", "Iterations") == 3
    with pytest.raises(ValueError, match="whole number"):
        HeadMatchGuiApp._parse_positive_int(app, "x", "Iterations")
    with pytest.raises(ValueError, match="greater than 0"):
        HeadMatchGuiApp._parse_positive_int(app, "0", "Iterations")


def test_refresh_basic_mode_target_step_only_rerenders_target_view():
    called = []
    app = SimpleNamespace(current_view=DummyVar(value="basic-mode"), basic_step_var=DummyVar(value="target"), show_view=lambda key: called.append(key))
    HeadMatchGuiApp.refresh_basic_mode_target_step(app)
    assert called == ["basic-mode"]

    called.clear()
    app.basic_step_var.set("measure")
    HeadMatchGuiApp.refresh_basic_mode_target_step(app)
    assert called == []


def test_choose_basic_search_match_rejects_invalid_index():
    app = SimpleNamespace(basic_search_matches=[], basic_search_results_var=DummyVar(value=""))
    HeadMatchGuiApp.choose_basic_search_match(app, 0)
    assert "Invalid" in app.basic_search_results_var.get()


def test_choose_basic_search_match_downloads_selection(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr("headmatch.paths.documents_dir", lambda: tmp_path)
    monkeypatch.setattr("headmatch.gui.shell.fetch_curve_from_url", lambda url, out_path: calls.update({"url": url, "out": Path(out_path)}) or Path(out_path))
    refreshed = []
    app = SimpleNamespace(
        basic_search_matches=[HeadphoneEntry(name="HD 650", source="oratory1990", form_factor="over-ear", csv_path="results/oratory1990/over-ear/HD 650/HD 650.csv")],
        basic_search_results_var=DummyVar(value=""),
        basic_target_mode_var=DummyVar(value="flat"),
        basic_target_csv_var=DummyVar(value=""),
        basic_target_path_var=DummyVar(value=""),
        basic_search_choice_var=DummyVar(value=""),
        refresh_basic_mode_target_step=lambda: refreshed.append(True),
    )

    HeadMatchGuiApp.choose_basic_search_match(app, 0)

    assert calls["url"].startswith("https://")
    assert app.basic_target_mode_var.get() == "database"
    assert app.basic_target_csv_var.get().endswith("HD 650 - oratory1990.csv")
    assert app.basic_search_choice_var.get() == "HD 650 — oratory1990"
    assert refreshed == [True]


def test_choose_target_csv_sets_basic_mode_state():
    app = SimpleNamespace(
        basic_search_results_var=DummyVar(value="old"),
        target_csv_var=DummyVar(value="/tmp/target.csv"),
        state=SimpleNamespace(config_path=Path("/tmp/config.json")),
        basic_target_csv_var=DummyVar(value=""),
        basic_target_path_var=DummyVar(value=""),
        basic_target_mode_var=DummyVar(value="flat"),
        refresh_basic_mode_target_step=lambda: None,
        _choose_file=lambda variable, **kwargs: None,
    )

    HeadMatchGuiApp.choose_target_csv(app)

    assert app.basic_search_results_var.get() == ""
    assert app.basic_target_csv_var.get() == "/tmp/target.csv"
    assert app.basic_target_path_var.get() == "/tmp/target.csv"
    assert app.basic_target_mode_var.get() == "csv"


def test_nav_items_for_mode_switches_between_basic_and_advanced():
    app = SimpleNamespace(mode_var=DummyVar(value="basic"))
    items = HeadMatchGuiApp._nav_items_for_mode(app)
    assert items[0].key == "basic-mode"

    app.mode_var.set("advanced")
    items = HeadMatchGuiApp._nav_items_for_mode(app)
    assert items[0].key == "measure-online"
