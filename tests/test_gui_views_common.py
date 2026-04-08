from __future__ import annotations

from types import SimpleNamespace

from headmatch.gui.views.common import _confidence_badge, _confidence_display, add_combobox_row, add_entry_row, add_picker_row, add_readonly_row
from tests.test_gui import DummyVar, DummyWidget, RecordingTtk


def test_confidence_display_helpers():
    assert _confidence_display("very_high") == "Very High"
    assert _confidence_badge("high").startswith("✓")
    assert _confidence_badge("unknown") == "Unknown"


def test_add_readonly_row_creates_label_and_entry():
    ttk = RecordingTtk()
    add_readonly_row(ttk, DummyWidget(), 0, "Label", DummyVar("x"))
    kinds = [w.kind for w in ttk.created]
    assert kinds == ["Label", "Entry"]


def test_add_combobox_row_creates_combobox():
    ttk = RecordingTtk()
    add_combobox_row(ttk, DummyWidget(), 0, "Mode", DummyVar(""), ("a", "b"), empty_label="")
    assert [w.kind for w in ttk.created] == ["Label", "Combobox"]


def test_add_entry_and_picker_rows_create_expected_widgets():
    ttk = RecordingTtk()
    add_entry_row(ttk, DummyWidget(), 0, "Search", DummyVar("x"))
    add_picker_row(ttk, DummyWidget(), 1, "Target CSV", DummyVar("x"), button_text="Browse…", command=lambda: None)
    kinds = [w.kind for w in ttk.created]
    assert kinds.count("Label") == 2
    assert kinds.count("Entry") == 2
    assert kinds.count("Button") == 1
