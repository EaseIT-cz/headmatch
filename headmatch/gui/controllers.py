from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..apo_import import load_apo_preset
from ..apo_refine import refine_apo_preset
from ..contracts import FrontendConfig
from ..history import build_history_selection
from ..measure import OfflineMeasurementPlan, prepare_offline_measurement
from ..pipeline import build_clone_curve, iterative_measure_and_fit, process_single_measurement
from ..headphone_db import fetch_curve_from_url, search_headphone
from ..signals import SweepSpec
from ..settings import load_or_create_config, save_config
from ..target_editor import TargetEditor


@dataclass
class WorkflowControllers:
    app: object

    def build_history_selection(self):
        return build_history_selection(self.app.history_root_var.get(), self.app.state.config_path.parent)

    def refresh_setup_check(self) -> None:
        report = self.app._doctor_report_runner(
            self.app.state.config_path,
            FrontendConfig(
                default_output_dir=self.app.output_dir_var.get().strip() or None,
                preferred_target_csv=self.app.target_csv_var.get().strip() or None,
                pipewire_output_target=self.app._strip_device_label(self.app.output_target_var.get()) or None,
                pipewire_input_target=self.app._strip_device_label(self.app.input_target_var.get()) or None,
                sample_rate=self.app.state.sample_rate,
                duration_s=self.app.state.duration_s,
                f_start_hz=self.app.state.f_start_hz,
                f_end_hz=self.app.state.f_end_hz,
                pre_silence_s=self.app.state.pre_silence_s,
                post_silence_s=self.app.state.post_silence_s,
                amplitude=self.app.state.amplitude,
                start_iterations=self.app._parse_positive_int(self.app.iterations_var.get().strip(), "Iterations"),
                max_filters=self.app._parse_positive_int(self.app.max_filters_var.get().strip(), "Max PEQ filters"),
                mode=self.app.mode_var.get().strip() or self.app.state.mode,
            ),
        )
        self.app.doctor_report_var.set(report)
        if self.app.current_view.get() == "setup-check":
            for child in self.app.content.winfo_children():
                child.destroy()
            self.app._render_setup_check()

    def run_apo_refine(self) -> None:
        preset_path = self.app.apo_preset_var.get().strip()
        recording_path = self.app.apo_refine_recording_var.get().strip()
        out_dir = self.app.apo_refine_output_var.get().strip()
        target_path = self.app.apo_refine_target_var.get().strip() or None
        if not preset_path:
            self.app._show_status("Select an APO preset file in the Import section above.")
            return
        if not recording_path:
            self.app._show_status("Select a recording WAV to refine against.")
            return
        if not out_dir:
            self.app._show_status("Select an output folder.")
            return
        try:
            config, _, _ = load_or_create_config(self.app.state.config_path)
            spec = SweepSpec(sample_rate=config.sample_rate, duration_s=config.duration_s)
            report = refine_apo_preset(
                preset_path=preset_path,
                recording_wav=recording_path,
                sweep_spec=spec,
                out_dir=out_dir,
                target_path=target_path,
            )
            orig = report.get('original_error', {})
            self.app._show_status(
                f"Refined: L {orig.get('left_rms', 0):.1f}→{report['predicted_left_rms_error_db']:.1f} dB, "
                f"R {orig.get('right_rms', 0):.1f}→{report['predicted_right_rms_error_db']:.1f} dB → {out_dir}"
            )
        except Exception as exc:
            self.app._show_status(f"Refine failed: {exc}")

    def run_apo_import(self) -> None:
        preset_path = self.app.apo_preset_var.get().strip()
        out_dir = self.app.apo_output_dir_var.get().strip()
        if not preset_path or not out_dir:
            self.app._show_status("Please select both a preset file and output folder.")
            return
        try:
            from ..exporters import export_camilladsp_filters_yaml, export_camilladsp_filter_snippet_yaml, export_equalizer_apo_parametric_txt
            left_bands, right_bands = load_apo_preset(preset_path)
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            export_equalizer_apo_parametric_txt(out / 'equalizer_apo.txt', left_bands, right_bands)
            export_camilladsp_filters_yaml(out / 'camilladsp_full.yaml', left_bands, right_bands)
            export_camilladsp_filter_snippet_yaml(out / 'camilladsp_filters_only.yaml', left_bands, right_bands)
            self.app._show_status(f"Imported {len(left_bands)}L + {len(right_bands)}R filters → {out_dir}")
        except Exception as exc:
            self.app._show_status(f"Import failed: {exc}")

    def run_search_headphone(self) -> None:
        query = self.app.fetch_search_var.get().strip()
        if not query:
            self.app._show_status("Enter a headphone model name to search.")
            return
        try:
            results = search_headphone(query)
        except Exception as exc:
            self.app._show_status(f"Search failed: {exc}")
            return
        self.app._search_results_data = results
        for widget in self.app._search_results_frame.winfo_children():
            widget.destroy()
        if not results:
            self.app._ttk.Label(self.app._search_results_frame, text=f"No matches for '{query}'.").grid(row=0, column=0, sticky="w")
            return
        self.app._ttk.Label(self.app._search_results_frame, text=f"{len(results)} match{'es' if len(results) != 1 else ''} — select one to populate the URL:").grid(row=0, column=0, sticky="w")
        import tkinter as _tk
        listbox = _tk.Listbox(self.app._search_results_frame, height=min(len(results), 8), width=70)
        for entry in results[:50]:
            listbox.insert(_tk.END, f"{entry.name}  [{entry.source}, {entry.form_factor}]")
        listbox.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        scrollbar = self.app._ttk.Scrollbar(self.app._search_results_frame, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.bind("<<ListboxSelect>>", self.app._on_search_result_selected)
        self.app._search_results_list = listbox

    def run_fetch_curve(self) -> None:
        url = self.app.fetch_url_var.get().strip()
        out_path = self.app.fetch_output_var.get().strip()
        if not url or not out_path:
            self.app._show_status("Please enter both a URL and output path.")
            return
        try:
            result = fetch_curve_from_url(url, out_path)
            self.app._show_status(f"Saved to {result}")
        except Exception as exc:
            self.app._show_status(f"Fetch failed: {exc}")

    def start_basic_clone_target(self) -> None:
        source = self.app.basic_clone_source_var.get().strip()
        target = self.app.basic_clone_target_var.get().strip()
        out_path = self.app.basic_clone_output_var.get().strip()
        if not source or not target or not out_path:
            raise ValueError("Source, target, and output CSV paths are required.")
        self.app._run_background_task(
            task_name="basic-clone-target",
            progress_title="Creating clone target",
            progress_body="HeadMatch is building a relative clone target from the chosen measurement artifacts.",
            worker=lambda: build_clone_curve(source, target, out_path),
            on_success=lambda result: self.app._set_completion(
                title="Clone target ready",
                summary=f"Saved clone target to {out_path}.",
                result=None,
                steps=(
                    "Use the clone target CSV in the target selector for a follow-up fit.",
                    "Re-run the basic or advanced measurement flow against the generated target.",
                    "Keep the source and target measurement artifacts around for traceability.",
                ),
            ),
        )

    def start_basic_measurement(self) -> None:
        out_dir = self.app.output_dir_var.get().strip()
        self.app._run_background_task(
            task_name="basic-mode",
            progress_title="Running basic measurement",
            progress_body="Basic mode is using defaults: 48 kHz, 3 iterations, default devices, and up to 10 PEQ filters.",
            worker=lambda: iterative_measure_and_fit(output_dir=out_dir, sweep_spec=self.app._build_sweep(), target_path=(self.app.basic_target_csv_var.get().strip() if self.app.basic_target_mode_var.get() in {"csv", "database"} else None), output_target=None, input_target=None, iterations=3, max_filters=10, iteration_mode="average"),
            on_success=lambda result: self.app._set_completion(title="Basic mode complete", summary=f"Saved to {out_dir}.", result=result, steps=("Review the result", "Export to the default location", "Switch to Advanced for fine tuning")),
        )

    def start_online_measurement(self) -> None:
        output_dir = self.app.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Output folder is required.")
        iterations = self.app._parse_positive_int(self.app.iterations_var.get().strip(), "Iterations")
        max_filters = self.app._parse_positive_int(self.app.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.app.target_csv_var.get().strip() or None
        output_target = self.app._strip_device_label(self.app.output_target_var.get()) or None
        input_target = self.app._strip_device_label(self.app.input_target_var.get()) or None
        self.app._run_background_task(
            task_name="measure-online",
            progress_title="Running online measurement",
            progress_body=f"Working in {output_dir}. The GUI is running the shared online pipeline now: playback, record, analyze, fit, and export.",
            worker=lambda: self.app._online_runner(output_dir=output_dir, sweep_spec=self.app._build_sweep(), target_path=target_csv, output_target=output_target, input_target=input_target, iterations=iterations, max_filters=max_filters, iteration_mode=self.app.iteration_mode_var.get().strip() or 'independent'),
            on_success=lambda result: self.app._set_completion(title="Online measurement complete", summary=f"The guided online run finished in {output_dir}.", result=result, steps=(f"Review outputs in {output_dir}.", "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.", "If the wrong devices were used, rerun with clearer playback/capture target matches.")),
        )

    def start_offline_prepare(self) -> None:
        output_dir = self.app.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Package folder is required.")
        out_dir = Path(output_dir)
        notes = self.app.offline_notes_var.get().strip()
        self.app._run_background_task(
            task_name="prepare-offline",
            progress_title="Writing offline sweep package",
            progress_body=f"Preparing sweep.wav and measurement_plan.json in {out_dir}.",
            worker=lambda: prepare_offline_measurement(self.app._build_sweep(), OfflineMeasurementPlan(sweep_wav=out_dir / "sweep.wav", metadata_json=out_dir / "measurement_plan.json", notes=notes)),
            on_success=lambda result: self.app._set_completion(title="Offline package ready", summary=f"The recorder-first package was written to {out_dir}.", result=result, steps=(f"Play and record {out_dir / 'sweep.wav'} with your handheld recorder.", "Keep the full capture, including extra tail, and do not trim the WAV before fitting.", f"Then return here and run the offline fit into {self.app.offline_fit_output_var.get().strip() or (out_dir / 'fit')}")),
        )

    def start_offline_fit(self) -> None:
        recording = self.app.offline_recording_var.get().strip()
        if not recording:
            raise ValueError("Recorded WAV is required.")
        out_dir = self.app.offline_fit_output_var.get().strip()
        if not out_dir:
            raise ValueError("Fit output folder is required.")
        max_filters = self.app._parse_positive_int(self.app.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.app.target_csv_var.get().strip() or None
        self.app._run_background_task(
            task_name="fit",
            progress_title="Fitting imported offline recording",
            progress_body=f"Analyzing {recording} and exporting EQ outputs into {out_dir}.",
            worker=lambda: self.app._offline_fit_runner(recording, out_dir, self.app._build_sweep(), target_path=target_csv, max_filters=max_filters),
            on_success=lambda result: self.app._set_completion(title="Offline fit complete", summary=f"The imported recording was analyzed and fitted into {out_dir}.", result=result, steps=(f"Review outputs in {out_dir}.", "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.", "If the fit looks wrong, re-record without trimming and try again.")),
        )

    def save_current_config(self) -> None:
        config = FrontendConfig(
            default_output_dir=self.app.output_dir_var.get().strip() or None,
            preferred_target_csv=self.app.target_csv_var.get().strip() or None,
            pipewire_output_target=self.app._strip_device_label(self.app.output_target_var.get()) or None,
            pipewire_input_target=self.app._strip_device_label(self.app.input_target_var.get()) or None,
            sample_rate=self.app.state.sample_rate,
            duration_s=self.app.state.duration_s,
            f_start_hz=self.app.state.f_start_hz,
            f_end_hz=self.app.state.f_end_hz,
            pre_silence_s=self.app.state.pre_silence_s,
            post_silence_s=self.app.state.post_silence_s,
            amplitude=self.app.state.amplitude,
            start_iterations=self.app._parse_positive_int(self.app.iterations_var.get().strip(), "Iterations"),
            max_filters=self.app._parse_positive_int(self.app.max_filters_var.get().strip(), "Max PEQ filters"),
            mode=self.app.mode_var.get().strip() or self.app.state.mode,
        )
        save_config(config, self.app.state.config_path)
