from __future__ import annotations

import argparse
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    from tkinter import filedialog
except Exception:  # pragma: no cover
    filedialog = None

from .app_identity import get_app_identity
from .contracts import FrontendConfig
from .measure import (
    OfflineMeasurementPlan,
    collect_doctor_checks,
    collect_pipewire_target_selection,
    format_doctor_report,
    prepare_offline_measurement,
)
from .pipeline import iterative_measure_and_fit, process_single_measurement
from .history import build_history_selection
from .target_editor import TargetEditor
from .apo_import import load_apo_preset
from .headphone_db import fetch_curve_from_url
from . import gui_views
from .settings import load_or_create_config
from .signals import SweepSpec


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str


@dataclass(frozen=True)
class GuiState:
    version_display: str
    config_path: Path
    config_created: bool
    current_view: str
    default_output_dir: str
    preferred_target_csv: str
    pipewire_output_target: str
    pipewire_input_target: str
    start_iterations: int
    max_filters: int
    sample_rate: int
    duration_s: float
    f_start_hz: float
    f_end_hz: float
    pre_silence_s: float
    post_silence_s: float
    amplitude: float


ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]
OnlineRunner = Callable[..., list[dict]]
OfflinePrepareRunner = Callable[[SweepSpec, OfflineMeasurementPlan], dict]
OfflineFitRunner = Callable[..., dict]
DoctorReportRunner = Callable[[Path, FrontendConfig], str]


NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("measure-online", "Measure"),
    NavigationItem("setup-check", "Setup Check"),
    NavigationItem("prepare-offline", "Prepare Offline"),
    NavigationItem("target-editor", "Target Editor"),
    NavigationItem("import-apo", "Import APO"),
    NavigationItem("fetch-curve", "Fetch Curve"),
    NavigationItem("history", "Results"),
)


def build_doctor_report(config_path: Path, config: FrontendConfig) -> str:
    return format_doctor_report(collect_doctor_checks(config_path, config), config_path=config_path)



def load_gui_state(
    config_path: str | Path | None = None,
    *,
    config_loader: ConfigLoader = load_or_create_config,
) -> GuiState:
    identity = get_app_identity()
    config, resolved_path, created = config_loader(config_path)
    return GuiState(
        version_display=identity.version_display,
        config_path=Path(resolved_path),
        config_created=created,
        current_view="measure-online",
        default_output_dir=config.default_output_dir or "out/session_01",
        preferred_target_csv=config.preferred_target_csv or "",
        pipewire_output_target=config.pipewire_output_target or "",
        pipewire_input_target=config.pipewire_input_target or "",
        start_iterations=config.start_iterations,
        max_filters=config.max_filters,
        sample_rate=config.sample_rate,
        duration_s=config.duration_s,
        f_start_hz=config.f_start_hz,
        f_end_hz=config.f_end_hz,
        pre_silence_s=config.pre_silence_s,
        post_silence_s=config.post_silence_s,
        amplitude=config.amplitude,
    )


class HeadMatchGuiApp:
    def __init__(
        self,
        root,
        state: GuiState,
        *,
        online_runner: OnlineRunner = iterative_measure_and_fit,
        offline_prepare_runner: OfflinePrepareRunner = prepare_offline_measurement,
        offline_fit_runner: OfflineFitRunner = process_single_measurement,
        doctor_report_runner: DoctorReportRunner = build_doctor_report,
    ):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.state = state
        self._ttk = ttk
        self._online_runner = online_runner
        self._offline_prepare_runner = offline_prepare_runner
        self._offline_fit_runner = offline_fit_runner
        self._doctor_report_runner = doctor_report_runner
        self._task_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._active_task_name: str | None = None
        self._last_completion_steps: tuple[str, ...] = ()

        self.current_view = tk.StringVar(master=root, value=state.current_view)
        self.output_dir_var = tk.StringVar(master=root, value=state.default_output_dir)
        self.target_csv_var = tk.StringVar(master=root, value=state.preferred_target_csv)
        self.output_target_var = tk.StringVar(master=root, value=state.pipewire_output_target)
        self.input_target_var = tk.StringVar(master=root, value=state.pipewire_input_target)
        self.output_target_options: tuple[str, ...] = ()
        self.input_target_options: tuple[str, ...] = ()
        self.iterations_var = tk.StringVar(master=root, value=str(state.start_iterations))
        self.iteration_mode_var = tk.StringVar(master=root, value="independent")
        self.max_filters_var = tk.StringVar(master=root, value=str(state.max_filters))
        self.history_root_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser().parent))
        self.offline_recording_var = tk.StringVar(master=root, value="")
        self.offline_fit_output_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "fit"))
        self.offline_notes_var = tk.StringVar(master=root, value="")
        self.apo_preset_var = tk.StringVar(master=root, value="")
        self.apo_output_dir_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "imported"))
        self.fetch_url_var = tk.StringVar(master=root, value="")
        self.fetch_output_var = tk.StringVar(master=root, value="")
        self.target_editor = TargetEditor()
        self.target_editor_save_path_var = tk.StringVar(master=root, value="")
        self.progress_title_var = tk.StringVar(master=root, value="")
        self.progress_body_var = tk.StringVar(master=root, value="")
        self.completion_title_var = tk.StringVar(master=root, value="")
        self.completion_body_var = tk.StringVar(master=root, value="")
        self.doctor_report_var = tk.StringVar(master=root, value="")
        self.content = None

        self.root.title(f"HeadMatch {state.version_display}")
        self.root.minsize(880, 560)
        self._configure_theme_defaults()
        self._load_pipewire_target_options()
        self._build_shell()
        self.show_view(state.current_view)

    def build_history_selection(self):
        return build_history_selection(self.history_root_var.get(), self.state.config_path.parent)


    def _load_pipewire_target_options(self) -> None:
        selection = collect_pipewire_target_selection(
            FrontendConfig(
                pipewire_output_target=self.state.pipewire_output_target or None,
                pipewire_input_target=self.state.pipewire_input_target or None,
            )
        )
        self.output_target_options = tuple(target.node_name for target in selection.playback_targets)
        self.input_target_options = tuple(target.node_name for target in selection.capture_targets)
        self.output_target_var.set(selection.selected_playback)
        self.input_target_var.set(selection.selected_capture)

    def _configure_theme_defaults(self) -> None:
        style_factory = getattr(self._ttk, "Style", None)
        if style_factory is None:
            return
        styles = style_factory(self.root)
        try:
            current_theme = styles.theme_use()
        except Exception:
            current_theme = None
        if current_theme:
            styles.theme_use(current_theme)
        styles.configure("Title.TLabel", font=("TkDefaultFont", 14, "bold"))
        styles.configure("Heading.TLabel", font=("TkDefaultFont", 10, "bold"))

    def _build_shell(self) -> None:
        ttk = self._ttk
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, padding=(16, 14, 16, 10))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="HeadMatch", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=f"Version {self.state.version_display}", style="Heading.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(header, text="Guided headphone measurement, fitting, and results review.", wraplength=560, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        nav = ttk.Frame(root, padding=(12, 8, 8, 16), width=164)
        nav.grid(row=1, column=0, sticky="nsw")
        nav.grid_propagate(False)
        nav.columnconfigure(0, weight=1)
        ttk.Label(nav, text="Workflows", style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        for idx, item in enumerate(NAV_ITEMS, start=1):
            ttk.Button(nav, text=item.label, command=lambda key=item.key: self.show_view(key)).grid(
                row=idx, column=0, sticky="ew", pady=2
            )

        self.content = ttk.Frame(root, padding=(10, 8, 16, 16))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

    def show_view(self, key: str) -> None:
        self.current_view.set(key)
        for child in self.content.winfo_children():
            child.destroy()
        if key == "measure-online":
            self._render_online_wizard()
            return
        if key == "setup-check":
            self._render_setup_check()
            return
        if key == "prepare-offline":
            self._render_offline_wizard()
            return
        if key == "target-editor":
            self._render_target_editor()
            return
        if key == "import-apo":
            self._render_import_apo()
            return
        if key == "fetch-curve":
            self._render_fetch_curve()
            return
        if key == "history":
            self._render_history()
            return
        raise KeyError(key)

    def _render_online_wizard(self) -> None:
        gui_views.render_online_wizard(self._ttk, self.content, variables=self, on_start=self.start_online_measurement)

    def _render_setup_check(self) -> None:
        if not self.doctor_report_var.get().strip():
            self.refresh_setup_check()
        gui_views.render_setup_check(
            self._ttk,
            self.content,
            report=self.doctor_report_var.get(),
            on_refresh=self.refresh_setup_check,
            on_measure=lambda: self.show_view("measure-online"),
        )

    def _render_offline_wizard(self) -> None:
        gui_views.render_offline_wizard(
            self._ttk,
            self.content,
            variables=self,
            on_prepare=self.start_offline_prepare,
            on_fit=self.start_offline_fit,
        )

    def _render_progress(self) -> None:
        gui_views.render_progress(self._ttk, self.content, title=self.progress_title_var.get(), body=self.progress_body_var.get())

    def _render_completion(self) -> None:
        gui_views.render_completion(
            self._ttk,
            self.content,
            title=self.completion_title_var.get(),
            body=self.completion_body_var.get(),
            steps=self._last_completion_steps,
            on_home=lambda: self.show_view("measure-online"),
            on_history=lambda: self.show_view("history"),
        )

    def refresh_setup_check(self) -> None:
        report = self._doctor_report_runner(
            self.state.config_path,
            FrontendConfig(
                default_output_dir=self.output_dir_var.get().strip() or None,
                preferred_target_csv=self.target_csv_var.get().strip() or None,
                pipewire_output_target=self.output_target_var.get().strip() or None,
                pipewire_input_target=self.input_target_var.get().strip() or None,
                sample_rate=self.state.sample_rate,
                duration_s=self.state.duration_s,
                f_start_hz=self.state.f_start_hz,
                f_end_hz=self.state.f_end_hz,
                pre_silence_s=self.state.pre_silence_s,
                post_silence_s=self.state.post_silence_s,
                amplitude=self.state.amplitude,
                start_iterations=self._parse_positive_int(self.iterations_var.get().strip(), "Iterations"),
                max_filters=self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters"),
            ),
        )
        self.doctor_report_var.set(report)
        if self.current_view.get() == "setup-check":
            for child in self.content.winfo_children():
                child.destroy()
            gui_views.render_setup_check(
                self._ttk,
                self.content,
                report=report,
                on_refresh=self.refresh_setup_check,
                on_measure=lambda: self.show_view("measure-online"),
            )

    def _render_target_editor(self) -> None:
        def _save():
            path = self.target_editor_save_path_var.get().strip()
            if not path:
                if filedialog:
                    path = filedialog.asksaveasfilename(
                        title="Save target curve",
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    )
                if not path:
                    return
                self.target_editor_save_path_var.set(path)
            self.target_editor.save(path)
            self._show_status(f"Target saved to {path}")

        def _reset():
            self.target_editor = TargetEditor()
            self.show_view("target-editor")

        gui_views.render_target_editor(
            self._ttk,
            self.content,
            editor=self.target_editor,
            on_save=_save,
            on_reset=_reset,
            on_update=lambda: self.show_view("target-editor"),
        )

    def _render_import_apo(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Import APO preset", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Load an Equalizer APO parametric preset and re-export it as CamillaDSP and HeadMatch formats.",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        form = ttk.LabelFrame(frame, text="Import settings", padding=12)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        gui_views.add_picker_row(ttk, form, 0, "APO preset file", self.apo_preset_var,
                                 button_text="Browse…", command=self._choose_apo_preset)
        gui_views.add_picker_row(ttk, form, 1, "Output folder", self.apo_output_dir_var,
                                 button_text="Browse…", command=self._choose_apo_output_dir)
        ttk.Button(form, text="Import and export", command=self._run_apo_import).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _choose_apo_preset(self) -> None:
        if filedialog:
            path = filedialog.askopenfilename(
                title="Select APO preset",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if path:
                self.apo_preset_var.set(path)

    def _choose_apo_output_dir(self) -> None:
        if filedialog:
            path = filedialog.askdirectory(title="Select output folder")
            if path:
                self.apo_output_dir_var.set(path)

    def _run_apo_import(self) -> None:
        preset_path = self.apo_preset_var.get().strip()
        out_dir = self.apo_output_dir_var.get().strip()
        if not preset_path or not out_dir:
            self._show_status("Please select both a preset file and output folder.")
            return
        try:
            from .exporters import (
                export_camilladsp_filters_yaml,
                export_camilladsp_filter_snippet_yaml,
                export_equalizer_apo_parametric_txt,
            )
            left_bands, right_bands = load_apo_preset(preset_path)
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            export_equalizer_apo_parametric_txt(out / 'equalizer_apo.txt', left_bands, right_bands)
            export_camilladsp_filters_yaml(out / 'camilladsp_full.yaml', left_bands, right_bands)
            export_camilladsp_filter_snippet_yaml(out / 'camilladsp_filters_only.yaml', left_bands, right_bands)
            self._show_status(f"Imported {len(left_bands)}L + {len(right_bands)}R filters → {out_dir}")
        except Exception as exc:
            self._show_status(f"Import failed: {exc}")

    def _render_fetch_curve(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Fetch published curve", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Download a headphone frequency response CSV from a community database (AutoEQ, oratory1990, etc). Only HTTPS URLs are accepted.",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        form = ttk.LabelFrame(frame, text="Fetch settings", padding=12)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        gui_views.add_entry_row(ttk, form, 0, "CSV URL (HTTPS)", self.fetch_url_var)
        gui_views.add_picker_row(ttk, form, 1, "Save to", self.fetch_output_var,
                                 button_text="Browse…", command=self._choose_fetch_output)
        ttk.Button(form, text="Fetch and save", command=self._run_fetch_curve).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(
            frame,
            text="Tip: visit github.com/jaakkopasanen/AutoEq, find your headphone, copy the raw CSV URL.",
            wraplength=560,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(12, 0))

    def _choose_fetch_output(self) -> None:
        if filedialog:
            path = filedialog.asksaveasfilename(
                title="Save curve as",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if path:
                self.fetch_output_var.set(path)

    def _run_fetch_curve(self) -> None:
        url = self.fetch_url_var.get().strip()
        out_path = self.fetch_output_var.get().strip()
        if not url or not out_path:
            self._show_status("Please enter both a URL and output path.")
            return
        try:
            result = fetch_curve_from_url(url, out_path)
            self._show_status(f"Saved to {result}")
        except Exception as exc:
            self._show_status(f"Fetch failed: {exc}")

    def _show_status(self, message: str) -> None:
        """Show a transient status message at the bottom of the current view."""
        import tkinter as tk
        status = self._ttk.Label(self.content, text=message, wraplength=560, justify="left")
        status.grid(row=99, column=0, sticky="w", pady=(12, 0))
        self.root.after(8000, status.destroy)

    def _render_history(self) -> None:
        import tkinter as tk

        ttk = self._ttk
        frame = self.content
        frame.rowconfigure(3, weight=1)
        ttk.Label(frame, text="Results", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Browse recent runs by scanning for run_summary.json files.",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        controls = ttk.LabelFrame(frame, text="Search", padding=12)
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Search folder").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
        ttk.Entry(controls, textvariable=self.history_root_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))
        def _browse_history():
            if filedialog:
                path = filedialog.askdirectory(title="Select results folder")
                if path:
                    self.history_root_var.set(path)
                    self.show_view("history")
        ttk.Button(controls, text="Browse…", command=_browse_history).grid(row=0, column=2, sticky="e", padx=(8, 0), pady=(0, 8))
        ttk.Button(controls, text="Refresh", command=lambda: self.show_view("history")).grid(row=0, column=3, sticky="e", padx=(4, 0), pady=(0, 8))

        scroll_frame = ttk.Frame(frame)
        scroll_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        scroll_frame.columnconfigure(0, weight=1)
        scroll_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        results = ttk.Frame(canvas, padding=(0, 0, 4, 0))
        canvas_window = canvas.create_window((0, 0), window=results, anchor="nw")

        def _sync_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_width(event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        results.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _fit_width)

        selection = gui_views.render_history(self._ttk, results, history_root_var=self.history_root_var, config_path=self.state.config_path)
        gui_views.render_history_results(self._ttk, results, selection=selection)
        _sync_scroll_region()


    def _build_sweep(self) -> SweepSpec:
        return SweepSpec(
            sample_rate=self.state.sample_rate,
            duration_s=self.state.duration_s,
            f_start=self.state.f_start_hz,
            f_end=self.state.f_end_hz,
            pre_silence_s=self.state.pre_silence_s,
            post_silence_s=self.state.post_silence_s,
            amplitude=self.state.amplitude,
        )

    def _parse_positive_int(self, raw: str, label: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if value <= 0:
            raise ValueError(f"{label} must be greater than 0.")
        return value

    @staticmethod
    def _expanded_parent(value: str, fallback: str | Path) -> str:
        raw = value.strip()
        if raw:
            return str(Path(raw).expanduser().parent)
        return str(Path(fallback).expanduser())

    @staticmethod
    def _expanded_dir(value: str, fallback: str | Path) -> str:
        raw = value.strip()
        if raw:
            return str(Path(raw).expanduser())
        return str(Path(fallback).expanduser())

    def _choose_directory(self, variable, *, title: str, fallback: str | Path) -> None:
        if filedialog is None:
            return
        selected = filedialog.askdirectory(
            title=title,
            initialdir=self._expanded_dir(variable.get(), fallback),
            parent=getattr(self, 'root', None),
            mustexist=False,
        )
        if selected:
            variable.set(selected)

    def _choose_file(self, variable, *, title: str, filetypes, fallback: str | Path) -> None:
        if filedialog is None:
            return
        selected = filedialog.askopenfilename(
            title=title,
            initialdir=self._expanded_parent(variable.get(), fallback),
            parent=getattr(self, 'root', None),
            filetypes=filetypes,
        )
        if selected:
            variable.set(selected)

    def choose_output_dir(self) -> None:
        self._choose_directory(self.output_dir_var, title="Choose output folder", fallback=self.state.default_output_dir)

    def choose_target_csv(self) -> None:
        self._choose_file(
            self.target_csv_var,
            title="Choose target CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            fallback=self.state.config_path.parent,
        )

    def choose_offline_recording(self) -> None:
        self._choose_file(
            self.offline_recording_var,
            title="Choose recorded WAV",
            filetypes=(("WAV files", "*.wav"), ("All files", "*.*")),
            fallback=self.output_dir_var.get().strip() or self.state.default_output_dir,
        )

    def choose_offline_fit_output_dir(self) -> None:
        self._choose_directory(
            self.offline_fit_output_var,
            title="Choose fit output folder",
            fallback=self.output_dir_var.get().strip() or self.state.default_output_dir,
        )

    def start_online_measurement(self) -> None:
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Output folder is required.")
        iterations = self._parse_positive_int(self.iterations_var.get().strip(), "Iterations")
        max_filters = self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.target_csv_var.get().strip() or None
        output_target = self.output_target_var.get().strip() or None
        input_target = self.input_target_var.get().strip() or None

        self._run_background_task(
            task_name="measure-online",
            progress_title="Running online measurement",
            progress_body=f"Working in {output_dir}. The GUI is running the shared online pipeline now: playback, record, analyze, fit, and export.",
            worker=lambda: self._online_runner(
                output_dir=output_dir,
                sweep_spec=self._build_sweep(),
                target_path=target_csv,
                output_target=output_target,
                input_target=input_target,
                iterations=iterations,
                max_filters=max_filters,
                iteration_mode=self.iteration_mode_var.get().strip() or 'independent',
            ),
            on_success=lambda _result: self._set_completion(
                title="Online measurement complete",
                summary=f"The guided online run finished in {output_dir}.",
                steps=(
                    f"Review outputs in {output_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the wrong devices were used, rerun with clearer playback/capture target matches.",
                ),
            ),
        )

    def start_offline_prepare(self) -> None:
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Package folder is required.")
        out_dir = Path(output_dir)
        notes = self.offline_notes_var.get().strip()
        self._run_background_task(
            task_name="prepare-offline",
            progress_title="Writing offline sweep package",
            progress_body=f"Preparing sweep.wav and measurement_plan.json in {out_dir}.",
            worker=lambda: self._offline_prepare_runner(
                self._build_sweep(),
                OfflineMeasurementPlan(sweep_wav=out_dir / "sweep.wav", metadata_json=out_dir / "measurement_plan.json", notes=notes),
            ),
            on_success=lambda _result: self._set_completion(
                title="Offline package ready",
                summary=f"The recorder-first package was written to {out_dir}.",
                steps=(
                    f"Play and record {out_dir / 'sweep.wav'} with your handheld recorder.",
                    "Keep the full capture, including extra tail, and do not trim the WAV before fitting.",
                    f"Then return here and run the offline fit into {self.offline_fit_output_var.get().strip() or (out_dir / 'fit')}",
                ),
            ),
        )

    def start_offline_fit(self) -> None:
        recording = self.offline_recording_var.get().strip()
        if not recording:
            raise ValueError("Recorded WAV is required.")
        out_dir = self.offline_fit_output_var.get().strip()
        if not out_dir:
            raise ValueError("Fit output folder is required.")
        max_filters = self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.target_csv_var.get().strip() or None
        self._run_background_task(
            task_name="fit-offline",
            progress_title="Fitting imported offline recording",
            progress_body=f"Analyzing {recording} and exporting EQ outputs into {out_dir}.",
            worker=lambda: self._offline_fit_runner(recording, out_dir, self._build_sweep(), target_path=target_csv, max_filters=max_filters),
            on_success=lambda _result: self._set_completion(
                title="Offline fit complete",
                summary=f"The imported recording was analyzed and fitted into {out_dir}.",
                steps=(
                    f"Review outputs in {out_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the fit looks wrong, re-record without trimming and try again.",
                ),
            ),
        )

    def _run_background_task(self, *, task_name: str, progress_title: str, progress_body: str, worker: Callable[[], object], on_success: Callable[[object], None]) -> None:
        if self._active_task_name is not None:
            raise RuntimeError("Another workflow is already running.")
        self._active_task_name = task_name
        self.progress_title_var.set(progress_title)
        self.progress_body_var.set(progress_body)
        self.show_view_progress()

        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # pragma: no cover
                self._task_queue.put(("error", exc))
                return
            self._task_queue.put(("success", (on_success, result)))

        threading.Thread(target=target, daemon=True).start()
        self._schedule_task_poll()

    def show_view_progress(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self._render_progress()

    def _schedule_task_poll(self) -> None:
        if hasattr(self.root, "after"):
            self.root.after(100, self._poll_task_queue)
        else:
            self._poll_task_queue()

    def _poll_task_queue(self) -> None:
        try:
            event, payload = self._task_queue.get_nowait()
        except queue.Empty:
            if self._active_task_name is not None and hasattr(self.root, "after"):
                self.root.after(100, self._poll_task_queue)
            return

        self._active_task_name = None
        if event == "error":
            exc = payload
            self._set_completion(
                title="Workflow could not finish",
                summary=str(exc),
                steps=(
                    "Check the paths and device targets shown in the wizard.",
                    "If this was an online run, confirm PipeWire playback and capture work from the terminal too.",
                ),
            )
            return
        on_success, result = payload
        on_success(result)

    def _set_completion(self, *, title: str, summary: str, steps: tuple[str, ...]) -> None:
        self._last_completion_steps = steps
        self.completion_title_var.set(title)
        self.completion_body_var.set(summary)
        for child in self.content.winfo_children():
            child.destroy()
        self._render_completion()


def create_app(
    root=None,
    *,
    config_path: str | Path | None = None,
    config_loader: ConfigLoader = load_or_create_config,
    online_runner: OnlineRunner = iterative_measure_and_fit,
    offline_prepare_runner: OfflinePrepareRunner = prepare_offline_measurement,
    offline_fit_runner: OfflineFitRunner = process_single_measurement,
    doctor_report_runner: DoctorReportRunner = build_doctor_report,
):
    if root is None:
        import tkinter as tk

        root = tk.Tk()
    state = load_gui_state(config_path, config_loader=config_loader)
    return HeadMatchGuiApp(
        root,
        state,
        online_runner=online_runner,
        offline_prepare_runner=offline_prepare_runner,
        offline_fit_runner=offline_fit_runner,
        doctor_report_runner=doctor_report_runner,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headmatch-gui", description="Launch the HeadMatch desktop shell.")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to a JSON config file. Default: ~/.config/headmatch/config.json or $XDG_CONFIG_HOME/headmatch/config.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        app = create_app(config_path=args.config)
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            raise SystemExit(f"GUI could not start: {exc}") from exc
        raise
    app.root.mainloop()
