"""Cross-platform ttk theming for the HeadMatch GUI.

HeadMatch standardises on the bundled ``clam`` theme on every platform rather
than the OS-native theme. ``clam`` honours ``background`` / ``foreground`` /
``style.map`` customisation, whereas macOS's ``aqua`` ignores most of it (and
rejects options such as ``-background`` on ttk widgets — see
``headmatch.gui.widgets.theme_background``). Standardising on ``clam`` gives a
consistent, customisable look across platforms *and* sidesteps the aqua
pitfalls that previously crashed the hearing-test view.
"""
from __future__ import annotations

PALETTE = {
    "bg": "#f4f5f7",          # window / frame background
    "surface": "#ffffff",     # entries, text areas, cards
    "accent": "#3b6ea5",      # primary actions (calm slate-blue)
    "accent_active": "#2f5985",
    "accent_text": "#ffffff",
    "text": "#1f2430",
    "muted": "#6b7280",
    "border": "#d4d8e0",
    "disabled": "#9aa1ad",
}

BASE_FONT = ("TkDefaultFont", 10)
TITLE_FONT = ("TkDefaultFont", 16, "bold")
HEADING_FONT = ("TkDefaultFont", 10, "bold")
SUBTITLE_FONT = ("TkDefaultFont", 11)


def apply_theme(ttk, root=None, palette=None) -> bool:
    """Apply the HeadMatch ``clam``-based theme.

    Returns ``True`` when styling was applied, ``False`` when the toolkit
    exposes no ``Style`` factory (e.g. the mocked widgets used in tests), in
    which case the call is a no-op. Every individual styling call is guarded so
    that an unexpected platform never hard-fails GUI construction over cosmetics.
    """
    style_factory = getattr(ttk, "Style", None)
    if style_factory is None:
        return False

    p = {**PALETTE, **(palette or {})}
    styles = style_factory(root) if root is not None else style_factory()

    try:
        styles.theme_use("clam")
    except Exception:
        # 'clam' ships with Tk everywhere, but never hard-fail on theming:
        # fall back to whatever theme is already active.
        try:
            current = styles.theme_use()
            if current:
                styles.theme_use(current)
        except Exception:
            pass

    def _cfg(*args, **kwargs) -> None:
        try:
            styles.configure(*args, **kwargs)
        except Exception:
            pass

    def _map(*args, **kwargs) -> None:
        try:
            styles.map(*args, **kwargs)
        except Exception:
            pass

    _cfg(".", background=p["bg"], foreground=p["text"], font=BASE_FONT,
         bordercolor=p["border"], focuscolor=p["accent"])
    _cfg("TFrame", background=p["bg"])
    _cfg("TLabel", background=p["bg"], foreground=p["text"])
    _cfg("Title.TLabel", font=TITLE_FONT, foreground=p["text"])
    _cfg("Heading.TLabel", font=HEADING_FONT, foreground=p["muted"])
    _cfg("Subtitle.TLabel", font=SUBTITLE_FONT, foreground=p["muted"])

    _cfg("TButton", padding=(12, 6), background=p["surface"], foreground=p["text"],
         bordercolor=p["border"], focusthickness=1, focuscolor=p["accent"])
    _map("TButton",
         background=[("active", p["border"]), ("pressed", p["border"])],
         foreground=[("disabled", p["disabled"])])

    _cfg("Accent.TButton", padding=(14, 7), background=p["accent"],
         foreground=p["accent_text"], font=HEADING_FONT, bordercolor=p["accent"])
    _map("Accent.TButton",
         background=[("active", p["accent_active"]), ("pressed", p["accent_active"]),
                     ("disabled", p["border"])],
         foreground=[("disabled", p["disabled"])])

    _cfg("TEntry", fieldbackground=p["surface"], bordercolor=p["border"],
         foreground=p["text"], padding=4)
    _cfg("TCombobox", fieldbackground=p["surface"], background=p["surface"],
         bordercolor=p["border"], foreground=p["text"], padding=4)
    _cfg("TLabelframe", background=p["bg"], bordercolor=p["border"])
    _cfg("TLabelframe.Label", background=p["bg"], foreground=p["muted"], font=HEADING_FONT)
    _cfg("TCheckbutton", background=p["bg"], foreground=p["text"])
    _cfg("TRadiobutton", background=p["bg"], foreground=p["text"])
    _cfg("Vertical.TScrollbar", background=p["bg"], troughcolor=p["bg"], bordercolor=p["border"])

    if root is not None:
        try:
            root.configure(background=p["bg"])
        except Exception:
            pass
    return True
