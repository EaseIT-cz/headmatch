"""Create or check a Linux desktop shortcut for HeadMatch GUI."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


DESKTOP_ENTRY_TEMPLATE = """\
[Desktop Entry]
Version=1.0
Type=Application
Name=HeadMatch
Comment=Measure headphones and build conservative EQ profiles
Exec={gui_path}
Icon=audio-headphones
Terminal=false
Categories=AudioVideo;Audio;Utility;
Keywords=headphones;measurement;eq;audio;
StartupNotify=true
"""

DESKTOP_DIR = Path.home() / ".local" / "share" / "applications"
DESKTOP_FILENAME = "headmatch.desktop"


def find_gui_binary() -> str | None:
    """Find the headmatch-gui binary path."""
    found = shutil.which("headmatch-gui")
    if found:
        return found
    # Fallback: same prefix as the running Python
    candidate = Path(sys.executable).parent / "headmatch-gui"
    if candidate.exists():
        return str(candidate)
    return None


def desktop_shortcut_path() -> Path:
    return DESKTOP_DIR / DESKTOP_FILENAME


def shortcut_exists() -> bool:
    return desktop_shortcut_path().exists()


def create_shortcut(gui_path: str | None = None) -> Path:
    """Create a .desktop file in ~/.local/share/applications/."""
    if gui_path is None:
        gui_path = find_gui_binary()
    if gui_path is None:
        raise FileNotFoundError(
            "Could not find headmatch-gui binary. "
            "Make sure HeadMatch is installed and headmatch-gui is on your PATH."
        )
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    path = desktop_shortcut_path()
    path.write_text(DESKTOP_ENTRY_TEMPLATE.format(gui_path=gui_path), encoding="utf-8")
    path.chmod(0o755)
    return path


def remove_shortcut() -> bool:
    """Remove the desktop shortcut if it exists."""
    path = desktop_shortcut_path()
    if path.exists():
        path.unlink()
        return True
    return False
