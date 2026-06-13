"""Regression tests for headmatch.gui.widgets.theme_background.

These guard against the macOS 'aqua' crash where querying a ttk widget's
``-background`` option raises ``_tkinter.TclError: unknown option
"-background"`` (regression from TASK-116, hearing_test.py:130).
"""
from __future__ import annotations

import pytest

from headmatch.gui.widgets import theme_background


class _Style:
    def __init__(self, *, value=None, raises=False):
        self._value = value
        self._raises = raises

    def lookup(self, *_args, **_kwargs):
        if self._raises:
            raise RuntimeError("unknown option \"-background\"")  # mimics TclError
        return self._value


class _Ttk:
    def __init__(self, style):
        self._style = style

    def Style(self):
        return self._style


def test_returns_theme_background_when_available():
    ttk = _Ttk(_Style(value="#dcdcdc"))
    assert theme_background(ttk) == "#dcdcdc"


def test_falls_back_when_theme_reports_empty():
    # macOS aqua frequently returns "" from Style().lookup for background.
    ttk = _Ttk(_Style(value=""))
    assert theme_background(ttk) == "#ECECEC"
    assert theme_background(ttk, fallback="#ffffff") == "#ffffff"


def test_does_not_raise_when_lookup_fails():
    # The original bug: this code path raised TclError on macOS and crashed
    # the Tkinter callback. It must now degrade to the fallback instead.
    ttk = _Ttk(_Style(raises=True))
    assert theme_background(ttk, fallback="#ffffff") == "#ffffff"
