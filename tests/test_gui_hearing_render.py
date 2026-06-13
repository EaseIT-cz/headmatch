"""Smoke tests for the hearing-test GUI render path.

`render_hearing_test` had **4% coverage** and was where the macOS
`unknown option "-background"` crash lived. These tests drive the whole
INTRO -> TEST_L -> TEST_R -> RESULTS flow with a fake toolkit and a fake
threshold engine (the real engine is covered in test_hearing_test.py), and
guard against the aqua `cget("background")` regression.
"""
from __future__ import annotations

import sys
import types

import pytest

from headmatch.gui.views import hearing_test as ht
from headmatch.hearing_test import HearingProfile


# ── fake toolkit ──────────────────────────────────────────────────────────────

class _FakeVar:
    def __init__(self, master=None, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, value):
        self._v = value


class _FakeTkWidget:
    """Permissive stand-in for tk.Text / tk.Canvas."""
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs

    def grid(self, *a, **k):
        return self

    def insert(self, *a, **k):
        return None

    def configure(self, *a, **k):
        return None

    config = configure

    def __getattr__(self, name):
        return lambda *a, **k: None


_FAKE_TK = types.SimpleNamespace(StringVar=_FakeVar, Text=_FakeTkWidget, Canvas=_FakeTkWidget)


class _FakeTtkWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.command = kwargs.get("command")
        self.text = kwargs.get("text")
        self.style = kwargs.get("style")

    def grid(self, *a, **k):
        return self

    def columnconfigure(self, *a, **k):
        return None

    def configure(self, *a, **k):
        return None

    config = configure


class _FakeTtk:
    """Records every widget created so tests can find buttons by label."""
    def __init__(self):
        self.created: list[_FakeTtkWidget] = []

    def _make(self, *a, **k):
        w = _FakeTtkWidget(*a, **k)
        self.created.append(w)
        return w

    def Frame(self, *a, **k):
        return self._make(*a, **k)

    def Label(self, *a, **k):
        return self._make(*a, **k)

    def Button(self, *a, **k):
        return self._make(*a, **k)


class _FakeFrame:
    """Content frame with a synchronous-drainable `after` queue.

    `cget` always raises, mimicking macOS aqua's `unknown option "-background"`
    — if the render path ever touches `frame.cget` again, these tests fail.
    """
    def __init__(self):
        self._after: dict[str, object] = {}
        self._counter = 0

    def after(self, _ms, callback):
        self._counter += 1
        tid = f"after#{self._counter}"
        self._after[tid] = callback
        return tid

    def after_cancel(self, tid):
        self._after.pop(tid, None)

    def winfo_children(self):
        return []

    def columnconfigure(self, *a, **k):
        return None

    def rowconfigure(self, *a, **k):
        return None

    def cget(self, _key):
        raise RuntimeError('unknown option "-background"')

    def configure(self, *a, **k):
        return None


class _FakeBackend:
    def __init__(self):
        self.calls = 0

    def play_tone(self, *a, **k):
        self.calls += 1


class _FakeEngine:
    """Converges after a single response — decouples the view test from the
    real Hughson-Westlake staircase (which never terminates on all-misses)."""
    def __init__(self, freq_hz, start_level_dbfs=-20.0):
        self.freq_hz = freq_hz
        self.current_level_dbfs = start_level_dbfs
        self.threshold = -45.0
        self.ascending_run_count = 3
        self.done = False

    def record_response(self, _heard):
        self.done = True


# ── helpers ─────────────────────────────────────────────────────────────────

def _drain(frame, limit=10000):
    n = 0
    while frame._after:
        n += 1
        if n > limit:  # pragma: no cover - guard against a runaway flow
            raise RuntimeError("after-queue did not drain")
        tid = next(iter(frame._after))
        frame._after.pop(tid)()


def _find_last(ttk, text):
    for w in reversed(ttk.created):
        if w.text == text and w.command is not None:
            return w
    return None


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setitem(sys.modules, "tkinter", _FAKE_TK)
    monkeypatch.setattr(ht, "ThresholdEngine", _FakeEngine)
    saved = {}
    monkeypatch.setattr(ht, "save_hearing_profile", lambda p: saved.__setitem__("profile", p))
    events = {"complete": [], "cancel": 0}
    ttk = _FakeTtk()
    frame = _FakeFrame()

    def render():
        ht.render_hearing_test(
            ttk, frame,
            backend=_FakeBackend(),
            output_device=None,
            sample_rate=48000,
            on_complete=lambda p: events["complete"].append(p),
            on_cancel=lambda: events.__setitem__("cancel", events["cancel"] + 1),
        )

    return types.SimpleNamespace(ttk=ttk, frame=frame, render=render, events=events, saved=saved)


# ── tests ─────────────────────────────────────────────────────────────────────

def test_intro_renders_without_touching_frame_cget(harness):
    # The macOS regression: building the intro must not query frame.cget.
    harness.render()
    assert _find_last(harness.ttk, "Start Test") is not None
    assert _find_last(harness.ttk, "Cancel") is not None


def test_full_flow_timeout_path_reaches_results_and_completes(harness):
    harness.render()
    _find_last(harness.ttk, "Start Test").command()        # -> left ear intro
    for _ in range(2):                                      # left, then right ear
        _find_last(harness.ttk, "Ready — Start").command()
        _drain(harness.frame)
    save = _find_last(harness.ttk, "Save & Use for EQ")
    assert save is not None, "results screen never rendered"
    save.command()
    _drain(harness.frame)

    assert "profile" in harness.saved
    assert len(harness.events["complete"]) == 1
    profile = harness.events["complete"][0]
    assert isinstance(profile, HearingProfile)
    # Both ears measured across all seven unique frequencies.
    assert len(profile.left) == 7 and len(profile.right) == 7


def test_heard_response_path(harness):
    harness.render()
    _find_last(harness.ttk, "Start Test").command()
    _find_last(harness.ttk, "Ready — Start").command()     # first tone scheduled
    hear = _find_last(harness.ttk, "I hear it")
    assert hear is not None
    hear.command()                                         # _on_heard branch
    _drain(harness.frame)                                  # finish left via timeouts
    _find_last(harness.ttk, "Ready — Start").command()     # right ear
    _drain(harness.frame)
    _find_last(harness.ttk, "Save & Use for EQ").command()
    _drain(harness.frame)
    assert isinstance(harness.events["complete"][0], HearingProfile)


def test_stop_test_invokes_cancel(harness):
    harness.render()
    _find_last(harness.ttk, "Cancel").command()
    assert harness.events["cancel"] == 1


def test_save_without_applying_uses_cancel(harness):
    harness.render()
    _find_last(harness.ttk, "Start Test").command()
    for _ in range(2):
        _find_last(harness.ttk, "Ready — Start").command()
        _drain(harness.frame)
    _find_last(harness.ttk, "Save Without Applying").command()
    _drain(harness.frame)
    assert "profile" in harness.saved
    assert harness.events["cancel"] == 1
    assert harness.events["complete"] == []
