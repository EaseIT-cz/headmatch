"""Configuration workflow controller.

Handles setup checks, config persistence, and history management.
"""

from __future__ import annotations

from .base import BaseController


class ConfigurationController(BaseController):
    """Controller for configuration-related workflows.
    
    Handles:
    - Setup/doctor checks
    - Configuration persistence
    - History selection
    """
    
    def build_history_selection(self):
        """Build a history selection from the configured output directory."""
        from ...history import build_history_selection
        
        return build_history_selection(
            self.app.history_root_var.get(),
            self.app.state.config_path.parent
        )
    
    def refresh_setup_check(self) -> None:
        """Run doctor checks and update the setup check view."""
        from ...contracts import FrontendConfig
        
        report = self.app._doctor_report_runner(
            self.app.state.config_path,
            FrontendConfig(
                default_output_dir=self.app.output_dir_var.get().strip() or None,
                preferred_target_csv=self.app.target_csv_var.get().strip() or None,
                pipewire_output_target=self._strip_device_label(
                    self.app.output_target_var.get()
                ) or None,
                pipewire_input_target=self._strip_device_label(
                    self.app.input_target_var.get()
                ) or None,
                sample_rate=self.app.state.sample_rate,
                duration_s=self.app.state.duration_s,
                f_start_hz=self.app.state.f_start_hz,
                f_end_hz=self.app.state.f_end_hz,
                pre_silence_s=self.app.state.pre_silence_s,
                post_silence_s=self.app.state.post_silence_s,
                amplitude=self.app.state.amplitude,
                start_iterations=self._parse_positive_int(
                    self.app.iterations_var.get().strip(), "Iterations"
                ),
                max_filters=self._parse_positive_int(
                    self.app.max_filters_var.get().strip(), "Max PEQ filters"
                ),
                mode=self.app.mode_var.get().strip() or self.app.state.mode,
            ),
        )
        
        self.app.doctor_report_var.set(report)
        
        if self.app.current_view.get() == "setup-check":
            for child in self.app.content.winfo_children():
                child.destroy()
            self.app._render_setup_check()
    
    def save_current_config(self) -> None:
        """Persist current GUI settings to the config file."""
        from ...contracts import FrontendConfig
        from ...settings import save_config
        
        config = FrontendConfig(
            default_output_dir=self.app.output_dir_var.get().strip() or None,
            preferred_target_csv=self.app.target_csv_var.get().strip() or None,
            pipewire_output_target=self._strip_device_label(
                self.app.output_target_var.get()
            ) or None,
            pipewire_input_target=self._strip_device_label(
                self.app.input_target_var.get()
            ) or None,
            sample_rate=self.app.state.sample_rate,
            duration_s=self.app.state.duration_s,
            f_start_hz=self.app.state.f_start_hz,
            f_end_hz=self.app.state.f_end_hz,
            pre_silence_s=self.app.state.pre_silence_s,
            post_silence_s=self.app.state.post_silence_s,
            amplitude=self.app.state.amplitude,
            start_iterations=self._parse_positive_int(
                self.app.iterations_var.get().strip(), "Iterations"
            ),
            max_filters=self._parse_positive_int(
                self.app.max_filters_var.get().strip(), "Max PEQ filters"
            ),
            mode=self.app.mode_var.get().strip() or self.app.state.mode,
        )
        save_config(config, self.app.state.config_path)
