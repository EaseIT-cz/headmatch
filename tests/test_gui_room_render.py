"""Smoke tests for the room-correction GUI render path.

Room correction was fully implemented in `headmatch.room` and reachable from the
CLI (`room-measure` / `room-fit`), but no module under `headmatch/gui` referenced
a single one of its functions — the whole capability was invisible to GUI users.
These tests drive the render with a fake toolkit so the wiring cannot silently
come undone, and pin the two buttons to their callbacks.
"""
from __future__ import annotations

import types

from headmatch.gui.views.room import ROOM_STEPS, render_room_correction


class _FakeVar:
    def __init__(self, master=None, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, value):
        self._v = value


class _FakeTtkWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.command = kwargs.get("command")
        self.text = kwargs.get("text")

    def grid(self, *a, **k):
        return self

    def columnconfigure(self, *a, **k):
        return None

    def configure(self, *a, **k):
        return None

    config = configure


class _FakeTtk:
    def __init__(self):
        self.created: list[_FakeTtkWidget] = []

    def _make(self, *a, **k):
        w = _FakeTtkWidget(*a, **k)
        self.created.append(w)
        return w

    Frame = Label = Button = Checkbutton = Entry = LabelFrame = _make

    def buttons(self):
        return [w for w in self.created if w.command is not None]


def _variables():
    return types.SimpleNamespace(
        room_output_var=_FakeVar(value="/tmp/room"),
        room_fit_output_var=_FakeVar(value="/tmp/room/fit"),
        room_recording_var=_FakeVar(),
        room_recording_two_var=_FakeVar(),
        room_mic_cal_var=_FakeVar(),
        room_target_csv_var=_FakeVar(),
        room_cutoff_hz_var=_FakeVar(value="300"),
        room_max_boost_db_var=_FakeVar(value="2.0"),
        room_two_positions_var=_FakeVar(value="0"),
        choose_room_output_dir=lambda: None,
        choose_room_fit_output_dir=lambda: None,
        choose_room_recording=lambda: None,
        choose_room_recording_two=lambda: None,
        choose_room_mic_cal=lambda: None,
        choose_room_target_csv=lambda: None,
    )


def test_render_room_correction_wires_both_actions():
    ttk = _FakeTtk()
    fired: list[str] = []
    render_room_correction(
        ttk,
        _FakeTtkWidget(),
        variables=_variables(),
        on_prepare=lambda: fired.append("prepare"),
        on_fit=lambda: fired.append("fit"),
    )

    # Both halves of the workflow must be reachable. A view that renders the
    # package step but not the fit step would look complete and dead-end the user.
    labelled = {w.text: w for w in ttk.created if w.text}
    assert "Write room sweep package" in labelled
    assert "Fit room correction" in labelled

    labelled["Write room sweep package"].command()
    labelled["Fit room correction"].command()
    assert fired == ["prepare", "fit"]


def test_render_room_correction_explains_it_is_for_speakers():
    """The one thing a headphone-EQ user can get badly wrong."""
    ttk = _FakeTtk()
    render_room_correction(
        ttk, _FakeTtkWidget(), variables=_variables(),
        on_prepare=lambda: None, on_fit=lambda: None,
    )
    prose = " ".join(w.text for w in ttk.created if isinstance(w.text, str))
    assert "speakers" in prose.lower()
    assert "not headphones" in prose.lower()


def test_room_steps_are_rendered():
    ttk = _FakeTtk()
    render_room_correction(
        ttk, _FakeTtkWidget(), variables=_variables(),
        on_prepare=lambda: None, on_fit=lambda: None,
    )
    prose = " ".join(w.text for w in ttk.created if isinstance(w.text, str))
    for step in ROOM_STEPS:
        assert step in prose
