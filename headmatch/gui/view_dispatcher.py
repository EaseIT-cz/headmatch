"""View dispatching logic for the HeadMatch GUI.

This module handles view routing and rendering delegation,
separating navigation logic from the main shell class.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shell import HeadMatchGuiApp

from .views import (
    render_basic_mode,
    render_clone_target_workflow,
    render_completion,
    render_fetch_curve,
    render_history_page,
    render_import_apo,
    render_offline_wizard,
    render_online_wizard,
    render_progress,
    render_setup_check,
    render_target_editor,
)
from .navigation import nav_items_for_mode


class ViewDispatcher:
    """Handles view routing and rendering for the GUI application.
    
    This class extracts the view dispatching logic from the main shell,
    providing a cleaner separation of concerns.
    """
    
    def __init__(self, app: "HeadMatchGuiApp") -> None:
        """Initialize the dispatcher with a reference to the app.
        
        Args:
            app: The HeadMatchGuiApp instance
        """
        self._app = app
    
    def render_nav_buttons(self) -> None:
        """Render the navigation buttons for the current mode."""
        for child in self._app.nav_buttons_frame.winfo_children():
            child.destroy()
        for idx, item in enumerate(nav_items_for_mode(self._app.mode_var.get())):
            self._app._ttk.Button(
                self._app.nav_buttons_frame,
                text=item.label,
                command=lambda key=item.key: self._app.show_view(key)
            ).grid(row=idx, column=0, sticky="ew", pady=2)
    
    def show_view(self, key: str) -> None:
        """Dispatch to the appropriate view renderer based on key.
        
        Args:
            key: The view identifier to render
        """
        self._app.current_view.set(key)
        for child in self._app.content.winfo_children():
            child.destroy()
        
        # Dispatch table for views
        dispatch = {
            "basic-mode": self._render_basic_mode,
            "basic-clone-target": self._render_basic_clone_target,
            "measure-online": self._render_online_wizard,
            "setup-check": self._render_setup_check,
            "prepare-offline": self._render_offline_wizard,
            "target-editor": self._render_target_editor,
            "import-apo": self._render_import_apo,
            "fetch-curve": self._render_fetch_curve,
            "history": self._render_history,
        }
        
        renderer = dispatch.get(key)
        if renderer:
            renderer()
        else:
            raise KeyError(key)
    
    def _render_online_wizard(self) -> None:
        render_online_wizard(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_start=self._app.start_online_measurement
        )
    
    def _render_basic_mode(self) -> None:
        render_basic_mode(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_next=self._app.basic_next_step,
            on_back=self._app.basic_back_step,
            on_measure=self._app.start_basic_measurement,
            on_export=self._app.basic_export_results,
            on_search=self._app.basic_search_target,
        )
    
    def _render_basic_clone_target(self) -> None:
        render_clone_target_workflow(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_create=self._app.start_basic_clone_target,
            on_back=lambda: self._app.show_view("basic-mode"),
        )
    
    def _render_setup_check(self) -> None:
        if not self._app.doctor_report_var.get().strip():
            self._app.refresh_setup_check()
        render_setup_check(
            self._app._ttk,
            self._app.content,
            report=self._app.doctor_report_var.get(),
            on_refresh=self._app.refresh_setup_check,
            on_measure=lambda: self._app.show_view("measure-online"),
        )
    
    def _render_offline_wizard(self) -> None:
        render_offline_wizard(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_prepare=self._app.start_offline_prepare,
            on_fit=self._app.start_offline_fit,
        )
    
    def _render_progress(self) -> None:
        render_progress(
            self._app._ttk,
            self._app.content,
            title=self._app.progress_title_var.get(),
            body=self._app.progress_body_var.get()
        )
    
    def _render_completion(self) -> None:
        render_completion(
            self._app._ttk,
            self._app.content,
            title=self._app.completion_title_var.get(),
            body=self._app.completion_body_var.get(),
            steps=self._app._last_completion_steps,
            clipping_assessment=self._app._completion_clipping_assessment,
            on_home=lambda: self._app.show_view(
                "basic-mode" if self._app.mode_var.get() == "basic" else "measure-online"
            ),
            on_history=lambda: self._app.show_view("history"),
        )
    
    def _render_target_editor(self) -> None:
        def _save():
            path = self._app.target_editor_save_path_var.get().strip()
            if not path:
                path = self._app._file_picker.choose_save_file(
                    path,
                    title="Save target curve",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    fallback=self._app.state.config_path.parent,
                ) or ""
                if not path:
                    return
                self._app.target_editor_save_path_var.set(path)
            self._app.target_editor.save(path)
            self._app._show_status(f"Target saved to {path}")

        def _reset():
            from ..target_editor import TargetEditor
            self._app.target_editor = TargetEditor()
            self._app.show_view("target-editor")

        def _load():
            path = self._app._file_picker.choose_file(
                self._app.target_editor_save_path_var.get(),
                title="Load target curve",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                fallback=self._app.state.config_path.parent,
            )
            if not path:
                return
            try:
                from ..target_editor import TargetEditor
                self._app.target_editor = TargetEditor.from_csv(path)
                self._app.target_editor_save_path_var.set(path)
                self._app._show_status(f"Loaded {path}")
                self._app.show_view("target-editor")
            except Exception as exc:
                self._app._show_status(f"Failed to load: {exc}")

        render_target_editor(
            self._app._ttk,
            self._app.content,
            editor=self._app.target_editor,
            on_save=_save,
            on_reset=_reset,
            on_load=_load,
            on_update=lambda: self._app.show_view("target-editor"),
        )
    
    def _render_import_apo(self) -> None:
        render_import_apo(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_import=self._app._controllers.run_apo_import,
            on_refine=self._app._controllers.run_apo_refine,
            on_choose_preset=self._app._choose_apo_preset,
            on_choose_output=self._app._choose_apo_output_dir,
            on_choose_refine_recording=self._app._choose_refine_recording,
            on_choose_refine_target=self._app._choose_refine_target,
            on_choose_refine_output=self._app._choose_refine_output,
        )
    
    def _render_fetch_curve(self) -> None:
        view = render_fetch_curve(
            self._app._ttk,
            self._app.content,
            variables=self._app,
            on_search=self._app._controllers.run_search_headphone,
            on_choose_output=self._app._choose_fetch_output,
            on_fetch=self._app._controllers.run_fetch_curve,
        )
        self._app._search_results_frame = view["results_frame"]
        self._app._search_results_list = None
        self._app._search_results_data: list = []
    
    def _render_history(self) -> None:
        def _browse_history():
            path = self._app._file_picker.choose_directory(
                self._app.history_root_var.get(),
                title="Select results folder",
                fallback=self._app.state.default_output_dir
            )
            if path:
                self._app.history_root_var.set(path)
                self._app.show_view("history")

        render_history_page(
            self._app._ttk,
            self._app.content,
            history_root_var=self._app.history_root_var,
            config_path=self._app.state.config_path,
            on_browse=_browse_history,
            on_refresh=lambda: self._app.show_view("history"),
        )
    
    def show_view_progress(self) -> None:
        """Show the progress view."""
        for child in self._app.content.winfo_children():
            child.destroy()
        self._render_progress()
    
    def show_view_completion(self) -> None:
        """Show the completion view."""
        for child in self._app.content.winfo_children():
            child.destroy()
        self._render_completion()
