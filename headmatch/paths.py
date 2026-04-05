"""Platform-aware config and cache directory helpers.

Linux:   XDG_CONFIG_HOME / ~/.config/headmatch,  XDG_CACHE_HOME / ~/.cache/headmatch
macOS:   ~/Library/Application Support/headmatch, ~/Library/Caches/headmatch
Windows: %APPDATA%/headmatch,                     %LOCALAPPDATA%/headmatch/cache
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-appropriate config directory, creating it if needed."""
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "headmatch"
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA")
        d = Path(base) / "headmatch" if base else Path.home() / ".config" / "headmatch"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        d = Path(xdg).expanduser() / "headmatch" if xdg else Path.home() / ".config" / "headmatch"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    """Return the platform-appropriate cache directory, creating it if needed."""
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Caches" / "headmatch"
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        d = Path(base) / "headmatch" / "cache" if base else Path.home() / ".cache" / "headmatch"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        d = Path(xdg) / "headmatch" if xdg else Path.home() / ".cache" / "headmatch"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        import tempfile
        d = Path(tempfile.gettempdir()) / "headmatch-cache"
        d.mkdir(parents=True, exist_ok=True)
        return d
