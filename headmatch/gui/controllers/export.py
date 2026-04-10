"""Export workflow controller.

Handles APO import/refine, curve fetching, and headphone database search.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseController


class ExportController(BaseController):
    """Controller for export-related workflows.
    
    Handles:
    - APO preset import
    - APO preset refinement against recording
    - Headphone database search
    - Curve fetching from URLs
    """
    
    def run_apo_import(self) -> None:
        """Import an APO preset and export to multiple formats."""
        from ...apo_import import load_apo_preset
        from ...exporters import (
            export_camilladsp_filters_yaml,
            export_camilladsp_filter_snippet_yaml,
            export_equalizer_apo_parametric_txt,
        )
        
        preset_path = self.app.apo_preset_var.get().strip()
        out_dir = self.app.apo_output_dir_var.get().strip()
        
        if not preset_path or not out_dir:
            self._show_status("Please select both a preset file and output folder.")
            return
        
        try:
            left_bands, right_bands = load_apo_preset(preset_path)
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            
            export_equalizer_apo_parametric_txt(
                out / 'equalizer_apo.txt', left_bands, right_bands
            )
            export_camilladsp_filters_yaml(
                out / 'camilladsp_full.yaml', left_bands, right_bands
            )
            export_camilladsp_filter_snippet_yaml(
                out / 'camilladsp_filters_only.yaml', left_bands, right_bands
            )
            
            self._show_status(
                f"Imported {len(left_bands)}L + {len(right_bands)}R filters → {out_dir}"
            )
        except Exception as exc:
            self._show_status(f"Import failed: {exc}")
    
    def run_apo_refine(self) -> None:
        """Refine an APO preset against a recording."""
        from ...apo_refine import refine_apo_preset
        from ...signals import SweepSpec
        from ...settings import load_or_create_config
        
        preset_path = self.app.apo_preset_var.get().strip()
        recording_path = self.app.apo_refine_recording_var.get().strip()
        out_dir = self.app.apo_refine_output_var.get().strip()
        target_path = self.app.apo_refine_target_var.get().strip() or None
        
        if not preset_path:
            self._show_status("Select an APO preset file in the Import section above.")
            return
        if not recording_path:
            self._show_status("Select a recording WAV to refine against.")
            return
        if not out_dir:
            self._show_status("Select an output folder.")
            return
        
        try:
            config, _, _ = load_or_create_config(self.app.state.config_path)
            spec = SweepSpec(
                sample_rate=config.sample_rate,
                duration_s=config.duration_s
            )
            report = refine_apo_preset(
                preset_path=preset_path,
                recording_wav=recording_path,
                sweep_spec=spec,
                out_dir=out_dir,
                target_path=target_path,
            )
            
            orig = report.get('original_error', {})
            self._show_status(
                f"Refined: L {orig.get('left_rms', 0):.1f}"
                f"→{report['predicted_left_rms_error_db']:.1f} dB, "
                f"R {orig.get('right_rms', 0):.1f}"
                f"→{report['predicted_right_rms_error_db']:.1f} dB → {out_dir}"
            )
        except Exception as exc:
            self._show_status(f"Refine failed: {exc}")
    
    def run_search_headphone(self) -> None:
        """Search the headphone database for matching models."""
        from ...headphone_db import search_headphone
        
        query = self.app.fetch_search_var.get().strip()
        if not query:
            self._show_status("Enter a headphone model name to search.")
            return
        
        try:
            results = search_headphone(query)
        except Exception as exc:
            self._show_status(f"Search failed: {exc}")
            return
        
        self.app._search_results_data = results
        
        # Clear previous results
        for widget in self.app._search_results_frame.winfo_children():
            widget.destroy()
        
        if not results:
            self.app._ttk.Label(
                self.app._search_results_frame,
                text=f"No matches for '{query}'."
            ).grid(row=0, column=0, sticky="w")
            return
        
        self.app._ttk.Label(
            self.app._search_results_frame,
            text=f"{len(results)} match{'es' if len(results) != 1 else ''} — select one to populate the URL:",
        ).grid(row=0, column=0, sticky="w")
        
        import tkinter as _tk
        listbox = _tk.Listbox(
            self.app._search_results_frame,
            height=min(len(results), 8),
            width=70
        )
        for entry in results[:50]:
            listbox.insert(
                _tk.END,
                f"{entry.name}  [{entry.source}, {entry.form_factor}]"
            )
        listbox.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        
        scrollbar = self.app._ttk.Scrollbar(
            self.app._search_results_frame,
            orient="vertical",
            command=listbox.yview
        )
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.bind("<<ListboxSelect>>", self.app._on_search_result_selected)
        self.app._search_results_list = listbox
    
    def run_fetch_curve(self) -> None:
        """Fetch a curve from URL and save to local file."""
        from ...headphone_db import fetch_curve_from_url
        
        url = self.app.fetch_url_var.get().strip()
        out_path = self.app.fetch_output_var.get().strip()
        
        if not url or not out_path:
            self._show_status("Please enter both a URL and output path.")
            return
        
        try:
            result = fetch_curve_from_url(url, out_path)
            self._show_status(f"Saved to {result}")
        except Exception as exc:
            self._show_status(f"Fetch failed: {exc}")
