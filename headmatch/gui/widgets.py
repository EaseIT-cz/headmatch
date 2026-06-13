"""Small shared helpers for building GUI widgets safely across platforms."""
from __future__ import annotations


def theme_background(ttk, fallback: str = "#ECECEC") -> str:
    """Resolve a usable background colour for plain ``tk`` widgets.

    Plain ``tk`` widgets (Text, Canvas, ...) often need a background colour
    that blends with the surrounding ``ttk`` frame. The obvious approach —
    ``frame.cget("background")`` — is a trap: ``ttk`` widgets do **not** expose
    a ``-background`` option on every platform. On macOS's ``aqua`` theme it
    raises ``_tkinter.TclError: unknown option "-background"``. (A ``hasattr``
    guard does not help: every Tk widget has a ``cget`` method.)

    Resolve the colour through the active ``ttk`` theme instead, falling back
    to a neutral default when the theme reports nothing usable.
    """
    try:
        bg = ttk.Style().lookup("TFrame", "background")
    except Exception:
        bg = None
    return str(bg) if bg else fallback
