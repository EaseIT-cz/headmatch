"""Centralized file picker helpers wrapping tkinter.filedialog."""
from __future__ import annotations

from typing import Any

# Import filedialog in a way that makes it mockable in tests
# Even if tkinter is not available, we define the module structure
# so that tests can mock it with @patch
try:
    import tkinter.filedialog as filedialog
except ImportError:
    # For headless testing - create a mockable placeholder
    class MockFileDialog:
        @staticmethod
        def askopenfilename(*args, **kwargs) -> str:
            raise ImportError("tkinter not available")

        @staticmethod
        def asksaveasfilename(*args, **kwargs) -> str:
            raise ImportError("tkinter not available")

        @staticmethod
        def askdirectory(*args, **kwargs) -> str:
            raise ImportError("tkinter not available")

    filedialog = MockFileDialog()  # type: ignore


def get_open_filename(
    parent: Any | None,
    title: str,
    filetypes: list[tuple[str, str]],
    initialdir: str | None = None,
) -> str | None:
    """Show a file open dialog and return the selected file path.
    
    Args:
        parent: Parent widget (None for headless testing)
        title: Dialog title
        filetypes: List of (description, pattern) tuples
        initialdir: Initial directory to open
        
    Returns:
        Selected file path or None if cancelled
    """
    result = filedialog.askopenfilename(
        parent=parent,
        title=title,
        filetypes=filetypes,
        initialdir=initialdir,
    )
    return result if result else None


def get_save_filename(
    parent: Any | None,
    title: str,
    defaultextension: str,
    filetypes: list[tuple[str, str]],
    initialdir: str | None = None,
) -> str | None:
    """Show a file save dialog and return the selected file path.
    
    Args:
        parent: Parent widget (None for headless testing)
        title: Dialog title
        defaultextension: Default file extension
        filetypes: List of (description, pattern) tuples
        initialdir: Initial directory to open
        
    Returns:
        Selected file path or None if cancelled
    """
    result = filedialog.asksaveasfilename(
        parent=parent,
        title=title,
        defaultextension=defaultextension,
        filetypes=filetypes,
        initialdir=initialdir,
    )
    return result if result else None


def get_directory(
    parent: Any | None,
    title: str,
    initialdir: str | None = None,
) -> str | None:
    """Show a directory selection dialog and return the selected path.
    
    Args:
        parent: Parent widget (None for headless testing)
        title: Dialog title
        initialdir: Initial directory to open
        
    Returns:
        Selected directory path or None if cancelled
    """
    result = filedialog.askdirectory(
        parent=parent,
        title=title,
        initialdir=initialdir,
    )
    return result if result else None