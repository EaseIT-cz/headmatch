"""Base controller class with shared functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class BaseController:
    """Base class for workflow controllers.
    
    Provides common utilities and app reference for all controllers.
    Controllers are responsible for business logic and state management,
    while views handle presentation.
    """
    
    def __init__(self, app) -> None:
        """Initialize the controller with reference to the GUI app.
        
        Args:
            app: The HeadMatchGuiApp instance
        """
        self._app = app
    
    @property
    def app(self):
        """Reference to the main GUI application."""
        return self._app
    
    def _strip_device_label(self, value: str) -> str:
        """Extract device ID from 'ID — Label' combo display string."""
        return self._app._strip_device_label(value)
    
    def _parse_positive_int(self, raw: str, label: str) -> int:
        """Parse a positive integer from a string input."""
        return self._app._parse_positive_int(raw, label)
    
    def _build_sweep(self):
        """Build a SweepSpec from current app state."""
        return self._app._build_sweep()
    
    def _show_status(self, message: str) -> None:
        """Show a transient status message in the GUI."""
        self._app._show_status(message)
