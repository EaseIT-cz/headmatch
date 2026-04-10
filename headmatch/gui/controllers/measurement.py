"""Measurement workflow controller.

Handles online measurement, offline preparation, and offline fitting workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseController

if TYPE_CHECKING:
    pass


class MeasurementController(BaseController):
    """Controller for measurement-related workflows.
    
    Handles:
    - Online (live) measurement workflow
    - Offline sweep package preparation
    - Offline recording fitting
    - Basic mode measurement
    - Clone target creation
    """
    
    def start_online_measurement(self) -> None:
        """Start an online (live) measurement and fitting workflow."""
        output_dir = self.app.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Output folder is required.")
        
        iterations = self._parse_positive_int(
            self.app.iterations_var.get().strip(), "Iterations"
        )
        max_filters = self._parse_positive_int(
            self.app.max_filters_var.get().strip(), "Max PEQ filters"
        )
        target_csv = self.app.target_csv_var.get().strip() or None
        output_target = self._strip_device_label(
            self.app.output_target_var.get()
        ) or None
        input_target = self._strip_device_label(
            self.app.input_target_var.get()
        ) or None
        
        self.app._run_background_task(
            task_name="measure-online",
            progress_title="Running online measurement",
            progress_body=f"Working in {output_dir}. The GUI is running the shared online pipeline now: playback, record, analyze, fit, and export.",
            worker=lambda: self.app._online_runner(
                output_dir=output_dir,
                sweep_spec=self._build_sweep(),
                target_path=target_csv,
                output_target=output_target,
                input_target=input_target,
                iterations=iterations,
                max_filters=max_filters,
                iteration_mode=self.app.iteration_mode_var.get().strip() or 'independent',
            ),
            on_success=lambda result: self.app._set_completion(
                title="Online measurement complete",
                summary=f"The guided online run finished in {output_dir}.",
                result=result,
                steps=(
                    f"Review outputs in {output_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the wrong devices were used, rerun with clearer playback/capture target matches.",
                ),
            ),
        )
    
    def start_basic_measurement(self) -> None:
        """Start a basic mode measurement with default settings."""
        out_dir = self.app.output_dir_var.get().strip()
        target_path = None
        if self.app.basic_target_mode_var.get() in {"csv", "database"}:
            target_path = self.app.basic_target_csv_var.get().strip()
        
        self.app._run_background_task(
            task_name="basic-mode",
            progress_title="Running basic measurement",
            progress_body="Basic mode is using defaults: 48 kHz, 3 iterations, default devices, and up to 10 PEQ filters.",
            worker=lambda: self.app._online_runner(
                output_dir=out_dir,
                sweep_spec=self._build_sweep(),
                target_path=target_path,
                output_target=None,
                input_target=None,
                iterations=3,
                max_filters=10,
                iteration_mode="average",
            ),
            on_success=lambda result: self.app._set_completion(
                title="Basic mode complete",
                summary=f"Saved to {out_dir}.",
                result=result,
                steps=(
                    "Review the result",
                    "Export to the default location",
                    "Switch to Advanced for fine tuning",
                ),
            ),
        )
    
    def start_offline_prepare(self) -> None:
        """Prepare an offline measurement package (sweep WAV + metadata)."""
        from ...measure import OfflineMeasurementPlan, prepare_offline_measurement
        
        output_dir = self.app.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Package folder is required.")
        
        out_dir = Path(output_dir)
        notes = self.app.offline_notes_var.get().strip()
        
        self.app._run_background_task(
            task_name="prepare-offline",
            progress_title="Writing offline sweep package",
            progress_body=f"Preparing sweep.wav and measurement_plan.json in {out_dir}.",
            worker=lambda: prepare_offline_measurement(
                self._build_sweep(),
                OfflineMeasurementPlan(
                    sweep_wav=out_dir / "sweep.wav",
                    metadata_json=out_dir / "measurement_plan.json",
                    notes=notes,
                ),
            ),
            on_success=lambda result: self.app._set_completion(
                title="Offline package ready",
                summary=f"The recorder-first package was written to {out_dir}.",
                result=result,
                steps=(
                    f"Play and record {out_dir / 'sweep.wav'} with your handheld recorder.",
                    "Keep the full capture, including extra tail, and do not trim the WAV before fitting.",
                    f"Then return here and run the offline fit into {self.app.offline_fit_output_var.get().strip() or (out_dir / 'fit')}",
                ),
            ),
        )
    
    def start_offline_fit(self) -> None:
        """Fit an imported offline recording."""
        recording = self.app.offline_recording_var.get().strip()
        if not recording:
            raise ValueError("Recorded WAV is required.")
        
        out_dir = self.app.offline_fit_output_var.get().strip()
        if not out_dir:
            raise ValueError("Fit output folder is required.")
        
        max_filters = self._parse_positive_int(
            self.app.max_filters_var.get().strip(), "Max PEQ filters"
        )
        target_csv = self.app.target_csv_var.get().strip() or None
        
        self.app._run_background_task(
            task_name="fit",
            progress_title="Fitting imported offline recording",
            progress_body=f"Analyzing {recording} and exporting EQ outputs into {out_dir}.",
            worker=lambda: self.app._offline_fit_runner(
                recording, 
                out_dir, 
                self._build_sweep(), 
                target_path=target_csv, 
                max_filters=max_filters
            ),
            on_success=lambda result: self.app._set_completion(
                title="Offline fit complete",
                summary=f"The imported recording was analyzed and fitted into {out_dir}.",
                result=result,
                steps=(
                    f"Review outputs in {out_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the fit looks wrong, re-record without trimming and try again.",
                ),
            ),
        )
    
    def start_basic_clone_target(self) -> None:
        """Create a clone target from source and target measurements."""
        from ...pipeline import build_clone_curve
        
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
