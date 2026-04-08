from __future__ import annotations

import argparse
import queue
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

try:
    from tkinter import filedialog
except Exception:  # pragma: no cover
    filedialog = None


def _get_filedialog():
    import sys
    gui_mod = sys.modules.get('headmatch.gui')
    return getattr(gui_mod, 'filedialog', filedialog)

from ..app_identity import get_app_identity
from ..contracts import FrontendConfig
from ..measure import OfflineMeasurementPlan, SweepSpec, collect_doctor_checks, collect_pipewire_target_selection, format_doctor_report, prepare_offline_measurement
from ..pipeline import build_clone_curve, iterative_measure_and_fit, process_single_measurement
from ..history import build_history_selection
from ..headphone_db import fetch_curve_from_url, search_headphone
from ..apo_import import load_apo_preset
from ..apo_refine import refine_apo_preset
from ..target_editor import TargetEditor
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
from ..settings import load_or_create_config
from .controllers import WorkflowControllers
from .services import BackgroundTaskService, FilePickerService


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
    mode: str
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


BASIC_NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("basic-mode", "Basic Workflow"),
    NavigationItem("basic-clone-target", "Clone Target"),
    NavigationItem("history", "Results"),
)

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
    import sys
    gui_mod = sys.modules.get('headmatch.gui')
    collect = getattr(gui_mod, 'collect_doctor_checks', collect_doctor_checks)
    format_report = getattr(gui_mod, 'format_doctor_report', format_doctor_report)
    return format_report(collect(config_path, config), config_path=config_path)



_LEGACY_OUTPUT_DIRS = {"out/session_01", "out\\session_01"}


def _resolve_default_output_dir(saved: str | None) -> str:
    """Return a sensible default output dir, ignoring legacy defaults."""
    if saved and saved.strip() not in _LEGACY_OUTPUT_DIRS:
        return saved
    return str(Path.home() / "Documents" / "HeadMatch" / "session_01")


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
        current_view="basic-mode" if config.mode == "basic" else "measure-online",
        mode=config.mode,
        default_output_dir=_resolve_default_output_dir(config.default_output_dir),
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
        self._controllers = WorkflowControllers(self)
        self._file_picker = FilePickerService(_get_filedialog(), root=root)
        self._background_tasks = BackgroundTaskService(task_queue=queue.Queue(), thread_factory=threading.Thread)
        self._task_queue = self._background_tasks.task_queue
        self._active_task_name: str | None = None
        self._last_completion_steps: tuple[str, ...] = ()
        self._completion_clipping_assessment: dict | None = None

        self.current_view = tk.StringVar(master=root, value=state.current_view)
        self.mode_var = tk.StringVar(master=root, value=state.mode)
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
        self.apo_refine_recording_var = tk.StringVar(master=root, value="")
        self.apo_refine_target_var = tk.StringVar(master=root, value="")
        self.apo_refine_output_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "refined"))
        self.fetch_url_var = tk.StringVar(master=root, value="")
        self.fetch_output_var = tk.StringVar(master=root, value="")
        self.fetch_search_var = tk.StringVar(master=root, value="")
        self.target_editor = TargetEditor()
        self.target_editor_save_path_var = tk.StringVar(master=root, value="")
        self.basic_step_var = tk.StringVar(master=root, value="target")
        self.basic_target_mode_var = tk.StringVar(master=root, value="flat")
        self.basic_search_query_var = tk.StringVar(master=root, value="")
        self.basic_search_results_var = tk.StringVar(master=root, value="")
        self.basic_target_csv_var = tk.StringVar(master=root, value=state.preferred_target_csv)
        self.basic_target_path_var = tk.StringVar(master=root, value="")
        self.basic_clone_source_var = tk.StringVar(master=root, value="")
        self.basic_clone_target_var = tk.StringVar(master=root, value="")
        self.basic_clone_output_var = tk.StringVar(master=root, value="")
        self.basic_progress_var = tk.StringVar(master=root, value="")
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
        controller = getattr(self, "_controllers", None)
        if controller is not None:
            return controller.build_history_selection()
        return build_history_selection(self.history_root_var.get(), self.state.config_path.parent)


    def _load_pipewire_target_options(self) -> None:
        import sys
        gui_mod = sys.modules.get('headmatch.gui')
        collect_targets = getattr(gui_mod, 'collect_pipewire_target_selection', collect_pipewire_target_selection)
        selection = collect_targets(
            FrontendConfig(
                pipewire_output_target=self.state.pipewire_output_target or None,
                pipewire_input_target=self.state.pipewire_input_target or None,
            )
        )
        self.output_target_options = tuple(f"{target.device_id} — {target.label}" for target in selection.playback_targets)
        self.input_target_options = tuple(f"{target.device_id} — {target.label}" for target in selection.capture_targets)
        # Resolve bare device IDs to display strings
        self.output_target_var.set(self._resolve_device_display(selection.selected_playback, self.output_target_options))
        self.input_target_var.set(self._resolve_device_display(selection.selected_capture, self.input_target_options))

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
        ttk.Label(nav, text="Mode", style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.mode_selector = ttk.Combobox(nav, textvariable=self.mode_var, values=("basic", "advanced"), state="readonly")
        self.mode_selector.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.mode_selector.bind("<<ComboboxSelected>>", lambda _evt: self.set_mode(self.mode_var.get()))
        ttk.Label(nav, text="Workflows", style="Heading.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.nav_buttons_frame = ttk.Frame(nav)
        self.nav_buttons_frame.grid(row=3, column=0, sticky="ew")
        self.nav_buttons_frame.columnconfigure(0, weight=1)
        self._render_nav_buttons()

        self.content = ttk.Frame(root, padding=(10, 8, 16, 16))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

    def _nav_items_for_mode(self) -> tuple[NavigationItem, ...]:
        return BASIC_NAV_ITEMS if self.mode_var.get() == "basic" else NAV_ITEMS

    def _render_nav_buttons(self) -> None:
        for child in self.nav_buttons_frame.winfo_children():
            child.destroy()
        for idx, item in enumerate(self._nav_items_for_mode()):
            self._ttk.Button(self.nav_buttons_frame, text=item.label, command=lambda key=item.key: self.show_view(key)).grid(
                row=idx, column=0, sticky="ew", pady=2
            )

    def show_view(self, key: str) -> None:
        self.current_view.set(key)
        for child in self.content.winfo_children():
            child.destroy()
        if key == "basic-mode":
            self._render_basic_mode()
            return
        if key == "basic-clone-target":
            self._render_basic_clone_target()
            return
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
        render_online_wizard(self._ttk, self.content, variables=self, on_start=self.start_online_measurement)

    def _render_basic_mode(self) -> None:
        render_basic_mode(
            self._ttk,
            self.content,
            variables=self,
            on_next=self.basic_next_step,
            on_back=self.basic_back_step,
            on_measure=self.start_basic_measurement,
            on_export=self.basic_export_results,
            on_search=self.basic_search_target,
        )

    def _render_basic_clone_target(self) -> None:
        render_clone_target_workflow(
            self._ttk,
            self.content,
            variables=self,
            on_create=self.start_basic_clone_target,
            on_back=lambda: self.show_view("basic-mode"),
        )

    def _render_setup_check(self) -> None:
        if not self.doctor_report_var.get().strip():
            self.refresh_setup_check()
        render_setup_check(
            self._ttk,
            self.content,
            report=self.doctor_report_var.get(),
            on_refresh=self.refresh_setup_check,
            on_measure=lambda: self.show_view("measure-online"),
        )

    def _render_offline_wizard(self) -> None:
        render_offline_wizard(
            self._ttk,
            self.content,
            variables=self,
            on_prepare=self.start_offline_prepare,
            on_fit=self.start_offline_fit,
        )

    def _render_progress(self) -> None:
        render_progress(self._ttk, self.content, title=self.progress_title_var.get(), body=self.progress_body_var.get())

    def _render_completion(self) -> None:
        render_completion(
            self._ttk,
            self.content,
            title=self.completion_title_var.get(),
            body=self.completion_body_var.get(),
            steps=self._last_completion_steps,
            clipping_assessment=self._completion_clipping_assessment,
            on_home=lambda: self.show_view("basic-mode" if self.mode_var.get() == "basic" else "measure-online"),
            on_history=lambda: self.show_view("history"),
        )

    def refresh_setup_check(self) -> None:
        self._controllers.refresh_setup_check()

    def _render_target_editor(self) -> None:
        def _save():
            path = self.target_editor_save_path_var.get().strip()
            if not path:
                path = self._file_picker.choose_save_file(
                    path,
                    title="Save target curve",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    fallback=self.state.config_path.parent,
                ) or ""
                if not path:
                    return
                self.target_editor_save_path_var.set(path)
            self.target_editor.save(path)
            self._show_status(f"Target saved to {path}")

        def _reset():
            self.target_editor = TargetEditor()
            self.show_view("target-editor")

        def _load():
            path = self._file_picker.choose_file(
                self.target_editor_save_path_var.get(),
                title="Load target curve",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                fallback=self.state.config_path.parent,
            )
            if not path:
                return
            try:
                self.target_editor = TargetEditor.from_csv(path)
                self.target_editor_save_path_var.set(path)
                self._show_status(f"Loaded {path}")
                self.show_view("target-editor")
            except Exception as exc:
                self._show_status(f"Failed to load: {exc}")

        render_target_editor(
            self._ttk,
            self.content,
            editor=self.target_editor,
            on_save=_save,
            on_reset=_reset,
            on_load=_load,
            on_update=lambda: self.show_view("target-editor"),
        )

    def _render_import_apo(self) -> None:
        render_import_apo(
            self._ttk, self.content, variables=self,
            on_import=self._controllers.run_apo_import, on_refine=self._controllers.run_apo_refine,
            on_choose_preset=self._choose_apo_preset,
            on_choose_output=self._choose_apo_output_dir,
            on_choose_refine_recording=self._choose_refine_recording,
            on_choose_refine_target=self._choose_refine_target,
            on_choose_refine_output=self._choose_refine_output,
        )

    def _choose_apo_preset(self) -> None:
        path = self._file_picker.choose_file(self.apo_preset_var.get(), title="Select APO preset", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], fallback=self.state.config_path.parent)
        if path:
            self.apo_preset_var.set(path)

    def _choose_apo_output_dir(self) -> None:
        path = self._file_picker.choose_directory(self.apo_output_dir_var.get(), title="Select output folder", fallback=self.state.default_output_dir)
        if path:
            self.apo_output_dir_var.set(path)

    def _choose_refine_recording(self) -> None:
        path = self._file_picker.choose_file(self.apo_refine_recording_var.get(), title="Select recording WAV", filetypes=[("WAV files", "*.wav"), ("All files", "*.*")], fallback=self.output_dir_var.get().strip() or self.state.default_output_dir)
        if path:
            self.apo_refine_recording_var.set(path)

    def _choose_refine_target(self) -> None:
        path = self._file_picker.choose_file(self.apo_refine_target_var.get(), title="Select target CSV (optional)", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], fallback=self.state.config_path.parent)
        if path:
            self.apo_refine_target_var.set(path)

    def _choose_refine_output(self) -> None:
        path = self._file_picker.choose_directory(self.apo_refine_output_var.get(), title="Select output folder for refined results", fallback=self.state.default_output_dir)
        if path:
            self.apo_refine_output_var.set(path)



    def _render_fetch_curve(self) -> None:
        view = render_fetch_curve(
            self._ttk, self.content, variables=self,
            on_search=self._controllers.run_search_headphone,
            on_choose_output=self._choose_fetch_output,
            on_fetch=self._controllers.run_fetch_curve,
        )
        self._search_results_frame = view["results_frame"]
        self._search_results_list = None
        self._search_results_data: list = []

    def _run_search_headphone(self) -> None:
        query = self.fetch_search_var.get().strip()
        if not query:
            self._show_status("Enter a headphone model name to search.")
            return
        try:
            results = search_headphone(query)
        except Exception as exc:
            self._show_status(f"Search failed: {exc}")
            return
        self._search_results_data = results
        # Clear previous results
        for widget in self._search_results_frame.winfo_children():
            widget.destroy()
        if not results:
            ttk = self._ttk
            ttk.Label(self._search_results_frame, text=f"No matches for '{query}'.").grid(row=0, column=0, sticky="w")
            return
        ttk = self._ttk
        ttk.Label(
            self._search_results_frame,
            text=f"{len(results)} match{'es' if len(results) != 1 else ''} — select one to populate the URL:",
        ).grid(row=0, column=0, sticky="w")
        import tkinter as _tk
        listbox = _tk.Listbox(self._search_results_frame, height=min(len(results), 8), width=70)
        for entry in results[:50]:
            listbox.insert(_tk.END, f"{entry.name}  [{entry.source}, {entry.form_factor}]")
        listbox.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        scrollbar = ttk.Scrollbar(self._search_results_frame, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.bind("<<ListboxSelect>>", self._on_search_result_selected)
        self._search_results_list = listbox

    def _on_search_result_selected(self, event) -> None:
        if not self._search_results_list:
            return
        selection = self._search_results_list.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self._search_results_data):
            entry = self._search_results_data[idx]
            self.fetch_url_var.set(entry.raw_csv_url)
            safe_name = entry.name.replace("/", "_").replace("\\", "_")
            from ..paths import documents_dir
            self.fetch_output_var.set(str(Path(documents_dir()) / f"{safe_name}.csv"))
            self.root.update_idletasks()
            self._show_status(f"Selected: {entry.name} — click \u2018Fetch and save\u2019 to download.")

    def _choose_fetch_output(self) -> None:
        path = self._file_picker.choose_save_file(self.fetch_output_var.get(), title="Save curve as", defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], fallback=self.state.config_path.parent)
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
        def _browse_history():
            path = self._file_picker.choose_directory(self.history_root_var.get(), title="Select results folder", fallback=self.state.default_output_dir)
            if path:
                self.history_root_var.set(path)
                self.show_view("history")

        render_history_page(
            self._ttk, self.content,
            history_root_var=self.history_root_var,
            config_path=self.state.config_path,
            on_browse=_browse_history,
            on_refresh=lambda: self.show_view("history"),
        )


    @staticmethod
    def _resolve_device_display(device_id: str, options: tuple[str, ...]) -> str:
        """Find the 'ID — Label' display string matching a bare device ID."""
        device_id = device_id.strip()
        for opt in options:
            if opt.startswith(device_id + " — "):
                return opt
        return device_id  # fallback to raw ID if no match

    @staticmethod
    def _strip_device_label(value: str) -> str:
        """Extract device ID from 'ID — Label' combo display string."""
        raw = value.strip()
        if " — " in raw:
            return raw.split(" — ", 1)[0].strip()
        return raw

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


    def _choose_directory(self, variable, *, title: str, fallback: str | Path) -> None:
        selected = self._file_picker.choose_directory(variable.get(), title=title, fallback=fallback)
        if selected:
            variable.set(selected)

    def _choose_file(self, variable, *, title: str, filetypes, fallback: str | Path) -> None:
        selected = self._file_picker.choose_file(variable.get(), title=title, filetypes=filetypes, fallback=fallback)
        if selected:
            variable.set(selected)


    def choose_basic_clone_source(self) -> None:
        self._choose_file(
            self.basic_clone_source_var,
            title="Choose source measurement CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            fallback=self.state.config_path.parent,
        )

    def choose_basic_clone_target(self) -> None:
        self._choose_file(
            self.basic_clone_target_var,
            title="Choose target measurement CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            fallback=self.state.config_path.parent,
        )

    def choose_basic_clone_output(self) -> None:
        self._choose_file(
            self.basic_clone_output_var,
            title="Choose clone target CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            fallback=self.state.config_path.parent,
        )

    def start_basic_clone_target(self) -> None:
        source = self.basic_clone_source_var.get().strip()
        target = self.basic_clone_target_var.get().strip()
        out_path = self.basic_clone_output_var.get().strip()
        if not source or not target or not out_path:
            raise ValueError("Source, target, and output CSV paths are required.")
        self._run_background_task(
            task_name="basic-clone-target",
            progress_title="Creating clone target",
            progress_body="HeadMatch is building a relative clone target from the chosen measurement artifacts.",
            worker=lambda: build_clone_curve(source, target, out_path),
            on_success=lambda result: self._set_completion(
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

    def choose_output_dir(self) -> None:
        self._choose_directory(self.output_dir_var, title="Choose output folder", fallback=self.state.default_output_dir)

    def choose_target_csv(self) -> None:
        self._choose_file(
            self.target_csv_var,
            title="Choose target CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            fallback=self.state.config_path.parent,
        )
        self.basic_target_csv_var.set(self.target_csv_var.get())
        self.basic_target_mode_var.set("csv")

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

    def set_mode(self, mode: str) -> None:
        self.mode_var.set(mode)
        # GuiState is frozen, so replace the entire state
        self.state = replace(self.state, mode=mode)
        self._save_current_config()
        self._render_nav_buttons()
        self.show_view("basic-mode" if mode == "basic" else "measure-online")

    def basic_next_step(self) -> None:
        self.basic_step_var.set({"target": "measure", "measure": "review", "review": "review"}.get(self.basic_step_var.get(), "target"))
        self.show_view("basic-mode")

    def basic_back_step(self) -> None:
        self.basic_step_var.set({"review": "measure", "measure": "target"}.get(self.basic_step_var.get(), "target"))
        self.show_view("basic-mode")

    def basic_search_target(self) -> None:
        query = self.basic_search_query_var.get().strip()
        if not query:
            self.basic_search_results_var.set("Enter a headphone model name to search the database.")
            return
        try:
            results = search_headphone(query)
        except Exception as exc:
            self.basic_search_results_var.set(f"Search failed: {exc}")
            return
        if not results:
            self.basic_search_results_var.set(f"No matches for '{query}'.")
            return
        entry = results[0]
        from ..paths import documents_dir
        safe_name = entry.name.replace("/", "_").replace("\\", "_")
        out_path = Path(documents_dir()) / f"{safe_name}.csv"
        try:
            saved = fetch_curve_from_url(entry.raw_csv_url, out_path)
        except Exception as exc:
            self.basic_search_results_var.set(f"Found {entry.name}, but download failed: {exc}")
            return
        self.basic_target_mode_var.set("database")
        self.basic_target_csv_var.set(str(saved))
        self.basic_target_path_var.set(str(saved))
        self.basic_search_results_var.set(f"Downloaded {entry.name} to {saved}.")

    def basic_export_results(self) -> None:
        self._show_status(f"Exported to {self.basic_export_path_var.get().strip() or self.output_dir_var.get().strip()}.")

    def start_basic_measurement(self) -> None:
        out_dir = self.output_dir_var.get().strip()
        self._run_background_task(
            task_name="basic-mode",
            progress_title="Running basic measurement",
            progress_body="Basic mode is using defaults: 48 kHz, 3 iterations, default devices, and up to 10 PEQ filters.",
            worker=lambda: self._online_runner(
                output_dir=out_dir,
                sweep_spec=self._build_sweep(),
                target_path=(self.basic_target_csv_var.get().strip() if self.basic_target_mode_var.get() == "csv" else None),
                output_target=None,
                input_target=None,
                iterations=3,
                max_filters=10,
                iteration_mode="average",
            ),
            on_success=lambda result: self._set_completion(
                title="Basic mode complete",
                summary=f"Saved to {out_dir}.",
                result=result,
                steps=("Review the result", "Export to the default location", "Switch to Advanced for fine tuning"),
            ),
        )

    def start_online_measurement(self) -> None:
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Output folder is required.")
        iterations = self._parse_positive_int(self.iterations_var.get().strip(), "Iterations")
        max_filters = self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.target_csv_var.get().strip() or None
        output_target = self._strip_device_label(self.output_target_var.get()) or None
        input_target = self._strip_device_label(self.input_target_var.get()) or None

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
            on_success=lambda result: self._set_completion(
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
            on_success=lambda result: self._set_completion(
                title="Offline package ready",
                summary=f"The recorder-first package was written to {out_dir}.",
                result=result,
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
            task_name="fit",
            progress_title="Fitting imported offline recording",
            progress_body=f"Analyzing {recording} and exporting EQ outputs into {out_dir}.",
            worker=lambda: self._offline_fit_runner(recording, out_dir, self._build_sweep(), target_path=target_csv, max_filters=max_filters),
            on_success=lambda result: self._set_completion(
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

    def _run_background_task(self, *, task_name: str, progress_title: str, progress_body: str, worker: Callable[[], object], on_success: Callable[[object], None]) -> None:
        if self._active_task_name is not None:
            raise RuntimeError("Another workflow is already running.")
        self._active_task_name = task_name
        self.progress_title_var.set(progress_title)
        self.progress_body_var.set(progress_body)
        self.show_view_progress()

        self._background_tasks.start(lambda: (on_success, worker()))
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
                    "If this was an online run, confirm audio playback and capture work from the terminal too.",
                ),
            )
            return
        on_success, result = payload
        on_success(result)

    def _save_current_config(self) -> None:
        """Persist current GUI settings to the config file."""
        try:
            self._controllers.save_current_config()
        except Exception:
            pass  # Config save is best-effort; don't interrupt the workflow

    def _set_completion(self, *, title: str, summary: str, steps: tuple[str, ...], result=None) -> None:
        self._last_completion_steps = steps
        self._completion_clipping_assessment = result.get("eq_clipping") if isinstance(result, dict) else None
        self.completion_title_var.set(title)
        self.completion_body_var.set(summary)
        self._save_current_config()
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
    import sys
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    app_factory = getattr(sys.modules.get('headmatch.gui'), 'create_app', create_app)
    try:
        app = app_factory(config_path=args.config)
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            raise SystemExit(f"GUI could not start: {exc}") from exc
        raise
    app.root.mainloop()
