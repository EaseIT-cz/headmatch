"""Workflow controllers registry.

Provides a unified interface to all workflow controllers, delegating
to specialized controllers for each workflow area.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .measurement import MeasurementController
from .export import ExportController
from .configuration import ConfigurationController

if TYPE_CHECKING:
    pass


class WorkflowControllers:
    """Registry for workflow controllers bound to a GUI app instance.
    
    This class provides backward compatibility with the existing
    WorkflowControllers API while delegating to specialized
    controller classes internally.
    """
    
    def __init__(self, app) -> None:
        self._app = app
        self._measurement = MeasurementController(app)
        self._export = ExportController(app)
        self._configuration = ConfigurationController(app)
    
    # Expose individual controllers
    @property
    def measurement(self) -> MeasurementController:
        """Access the measurement workflow controller."""
        return self._measurement
    
    @property
    def export(self) -> ExportController:
        """Access the export workflow controller."""
        return self._export
    
    @property
    def configuration(self) -> ConfigurationController:
        """Access the configuration workflow controller."""
        return self._configuration
    
    # Delegate to MeasurementController
    def start_online_measurement(self) -> None:
        """Start an online measurement workflow."""
        return self._measurement.start_online_measurement()
    
    def start_basic_measurement(self) -> None:
        """Start a basic mode measurement."""
        return self._measurement.start_basic_measurement()
    
    def start_offline_prepare(self) -> None:
        """Prepare an offline measurement package."""
        return self._measurement.start_offline_prepare()
    
    def start_offline_fit(self) -> None:
        """Fit an offline recording."""
        return self._measurement.start_offline_fit()
    
    def start_basic_clone_target(self) -> None:
        """Create a clone target."""
        return self._measurement.start_basic_clone_target()
    
    # Delegate to ExportController
    def run_apo_import(self) -> None:
        """Import an APO preset."""
        return self._export.run_apo_import()
    
    def run_apo_refine(self) -> None:
        """Refine an APO preset against a recording."""
        return self._export.run_apo_refine()
    
    def run_search_headphone(self) -> None:
        """Search the headphone database."""
        return self._export.run_search_headphone()
    
    def run_fetch_curve(self) -> None:
        """Fetch a curve from a URL."""
        return self._export.run_fetch_curve()
    
    # Delegate to ConfigurationController
    def build_history_selection(self):
        """Build history selection."""
        return self._configuration.build_history_selection()
    
    def refresh_setup_check(self) -> None:
        """Refresh the setup check display."""
        return self._configuration.refresh_setup_check()
    
    def save_current_config(self) -> None:
        """Save current configuration to disk."""
        return self._configuration.save_current_config()
