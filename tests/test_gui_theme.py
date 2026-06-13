"""Tests for headmatch.gui.theme.apply_theme."""
from __future__ import annotations

from headmatch.gui.theme import apply_theme, PALETTE


class _RecordingStyle:
    def __init__(self, master=None, *, theme_use_raises=False):
        self.master = master
        self._theme = "default"
        self._theme_use_raises = theme_use_raises
        self.configured: dict = {}
        self.mapped: dict = {}
        self.theme_calls: list = []

    def theme_use(self, name=None):
        if name is None:
            return self._theme
        if self._theme_use_raises and name == "clam":
            raise RuntimeError("no such theme")
        self.theme_calls.append(name)
        self._theme = name

    def configure(self, style, **kwargs):
        self.configured.setdefault(style, {}).update(kwargs)

    def map(self, style, **kwargs):
        self.mapped.setdefault(style, {}).update(kwargs)


class _Root:
    def __init__(self):
        self.background = None

    def configure(self, **kwargs):
        self.background = kwargs.get("background", self.background)


class _Ttk:
    def __init__(self, style):
        self._style = style

    def Style(self, master=None):
        self._style.master = master
        return self._style


def test_returns_false_without_style_factory():
    class NoStyle:
        pass

    assert apply_theme(NoStyle()) is False


def test_applies_clam_theme_and_core_styles():
    style = _RecordingStyle()
    root = _Root()
    assert apply_theme(_Ttk(style), root) is True
    assert "clam" in style.theme_calls
    # Core styles configured with the palette
    assert style.configured["TFrame"]["background"] == PALETTE["bg"]
    assert style.configured["Accent.TButton"]["background"] == PALETTE["accent"]
    assert "Accent.TButton" in style.mapped
    assert root.background == PALETTE["bg"]


def test_falls_back_when_clam_unavailable():
    # Must not raise even if 'clam' is rejected; styling still applied.
    style = _RecordingStyle(theme_use_raises=True)
    assert apply_theme(_Ttk(style), _Root()) is True
    assert "clam" not in style.theme_calls
    assert style.configured["TLabel"]["foreground"] == PALETTE["text"]


def test_custom_palette_override():
    style = _RecordingStyle()
    apply_theme(_Ttk(style), _Root(), palette={"accent": "#ff0000"})
    assert style.configured["Accent.TButton"]["background"] == "#ff0000"
