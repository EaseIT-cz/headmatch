"""GUI view for the hearing threshold test workflow."""
from __future__ import annotations

import threading
from typing import Callable, Optional

from ...hearing_test import (
    ASYMMETRY_WARNING_DB,
    GAIN_FRACTION,
    MAX_COMPENSATION_DB,
    NORMAL_HEARING_REFERENCE,
    RESPONSE_WINDOW_S,
    START_LEVEL_DBFS,
    TEST_FREQUENCIES,
    TEST_ORDER,
    FrequencyThreshold,
    HearingProfile,
    ThresholdEngine,
    detect_asymmetric_frequencies,
    generate_tone,
    save_hearing_profile,
)
from ..widgets import theme_background

from datetime import datetime, timezone


_FREQ_LABELS = {
    500: "500 Hz",
    1000: "1 kHz",
    2000: "2 kHz",
    3000: "3 kHz",
    4000: "4 kHz",
    6000: "6 kHz",
    8000: "8 kHz",
}


def render_hearing_test(
    ttk,
    frame,
    *,
    backend,
    output_device: Optional[str],
    sample_rate: int,
    on_complete: Callable[[HearingProfile], None],
    on_cancel: Callable[[], None],
) -> None:
    """
    Render the hearing test into frame.

    Manages the full INTRO → TEST_L → TEST_R → RESULTS flow inside frame.
    Calls on_complete(profile) when the user accepts results, or on_cancel()
    if they stop the test early.
    """
    import tkinter as tk

    _state: dict = {
        "ear": "left",
        "engine": None,
        "freq_index": 0,
        "processed_freqs": set(),
        "left": {},
        "right": {},
        "response_timer": None,
        "tone_thread": None,
        "responded": False,
    }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear():
        for child in frame.winfo_children():
            child.destroy()

    def _cancel_timer():
        timer_id = _state.get("response_timer")
        if timer_id is not None:
            try:
                frame.after_cancel(timer_id)
            except Exception:
                pass
            _state["response_timer"] = None

    def _play_tone_async(freq_hz: int, level_dbfs: float):
        """Play tone in a background thread so Tkinter stays responsive."""
        def _worker():
            try:
                samples = generate_tone(freq_hz, level_dbfs, sample_rate)
                backend.play_tone(samples, sample_rate, output_device)
            except Exception:
                pass
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        _state["tone_thread"] = t

    # ── view transitions ─────────────────────────────────────────────────────

    def _show_intro():
        _clear()
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Hearing Test", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(
            frame,
            text=(
                "This test sweeps pure tones across 7 frequencies in each ear "
                "and estimates where your hearing thresholds are. "
                "The result is used to personalise the EQ compensation applied "
                "to your headphone fit."
            ),
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        instructions = (
            "Before you start:",
            "  • Set your headphone volume to a comfortable music-listening level.",
            "  • Go to a quiet room.",
            "  • The test takes about 5 minutes total.",
            "",
            "During the test:",
            "  • Click 'I hear it' each time you hear a tone.",
            "  • If you don't hear the tone, do nothing — the test advances automatically.",
            "  • Test your LEFT ear first, then your RIGHT ear.",
        )
        info_text = tk.Text(
            frame, height=10, width=62, state="normal",
            relief="flat", background=theme_background(ttk),
            wrap="word",
        )
        info_text.insert("1.0", "\n".join(instructions))
        info_text.configure(state="disabled")
        info_text.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, sticky="w")
        ttk.Button(btn_frame, text="Start Test", command=_begin_left, style="Accent.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).grid(row=0, column=1)

    def _begin_left():
        _state["ear"] = "left"
        _state["processed_freqs"] = set()
        _state["freq_index"] = 0
        _show_ear_intro("left", callback=_start_test_loop)

    def _begin_right():
        _state["ear"] = "right"
        _state["processed_freqs"] = set()
        _state["freq_index"] = 0
        _show_ear_intro("right", callback=_start_test_loop)

    def _show_ear_intro(ear: str, callback: Callable):
        _clear()
        frame.columnconfigure(0, weight=1)
        cover = "right" if ear == "left" else "left"
        ttk.Label(frame, text=f"Testing {ear.capitalize()} Ear", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(
            frame,
            text=f"Cover or plug your {cover} ear. Click Ready when set.",
            wraplength=560,
        ).grid(row=1, column=0, sticky="w", pady=(0, 16))
        ttk.Button(frame, text="Ready — Start", command=callback, style="Accent.TButton").grid(row=2, column=0, sticky="w")
        ttk.Button(frame, text="Stop Test", command=_stop_test).grid(row=3, column=0, sticky="w", pady=(8, 0))

    # ── test loop ─────────────────────────────────────────────────────────────

    def _start_test_loop():
        _state["freq_index"] = 0
        _state["processed_freqs"] = set()
        _advance_to_next_freq()

    def _advance_to_next_freq():
        idx = _state["freq_index"]
        order = TEST_ORDER

        # Skip already-processed frequencies
        while idx < len(order) and order[idx] in _state["processed_freqs"]:
            idx += 1
        _state["freq_index"] = idx

        if idx >= len(order):
            _finish_ear()
            return

        freq_hz = order[idx]
        _state["processed_freqs"].add(freq_hz)
        _state["engine"] = ThresholdEngine(freq_hz, start_level_dbfs=START_LEVEL_DBFS)
        _show_test_screen(freq_hz, idx)
        _next_tone()

    def _show_test_screen(freq_hz: int, order_idx: int):
        _clear()
        frame.columnconfigure(0, weight=1)

        ear = _state["ear"]
        # Count unique frequencies done so far
        done_count = len(_state["processed_freqs"])
        total = len(TEST_FREQUENCIES)

        ttk.Label(frame, text=f"Testing {ear.capitalize()} Ear", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            frame,
            text=f"Frequency {done_count} / {total} — {_FREQ_LABELS.get(freq_hz, f'{freq_hz} Hz')}",
            style="Heading.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        # Speaker indicator
        _state["speaker_label_var"] = tk.StringVar(value="♪ Playing tone …")
        ttk.Label(frame, textvariable=_state["speaker_label_var"]).grid(
            row=2, column=0, sticky="w", pady=(0, 12)
        )

        # "I hear it" button — the only interaction
        hear_btn = ttk.Button(
            frame,
            text="I hear it",
            command=_on_heard,
        )
        hear_btn.grid(row=3, column=0, sticky="w", pady=(0, 8))
        _state["hear_btn"] = hear_btn

        ttk.Button(frame, text="Stop Test", command=_stop_test).grid(row=4, column=0, sticky="w", pady=(4, 0))

    def _next_tone():
        """Play the current tone and start the response window timer."""
        _cancel_timer()
        _state["responded"] = False

        engine: ThresholdEngine = _state["engine"]
        if engine.done:
            _on_freq_done()
            return

        freq_hz = engine.freq_hz
        level = engine.current_level_dbfs

        # Update speaker indicator
        speaker_var = _state.get("speaker_label_var")
        if speaker_var:
            speaker_var.set("♪ Playing tone …")

        _play_tone_async(freq_hz, level)

        # Response window: RESPONSE_WINDOW_S seconds from tone start
        timer_id = frame.after(
            int(RESPONSE_WINDOW_S * 1000),
            _on_timeout,
        )
        _state["response_timer"] = timer_id

    def _on_heard():
        if _state.get("responded"):
            return
        _state["responded"] = True
        _cancel_timer()
        engine: ThresholdEngine = _state["engine"]
        engine.record_response(True)
        speaker_var = _state.get("speaker_label_var")
        if speaker_var:
            speaker_var.set("✓ Heard")
        if engine.done:
            frame.after(300, _on_freq_done)
        else:
            frame.after(300, _next_tone)

    def _on_timeout():
        if _state.get("responded"):
            return
        _state["responded"] = True
        _state["response_timer"] = None
        engine: ThresholdEngine = _state["engine"]
        engine.record_response(False)
        speaker_var = _state.get("speaker_label_var")
        if speaker_var:
            speaker_var.set("— Not heard")
        if engine.done:
            frame.after(300, _on_freq_done)
        else:
            frame.after(300, _next_tone)

    def _on_freq_done():
        engine: ThresholdEngine = _state["engine"]
        freq_hz = engine.freq_hz
        threshold = engine.threshold
        determined = threshold is not None

        result = FrequencyThreshold(
            freq_hz=freq_hz,
            level_dbfs=threshold,
            ascending_runs=engine.ascending_run_count,
            determined=determined,
        )
        _state[_state["ear"]][freq_hz] = result

        # Advance freq_index past the current entry
        _state["freq_index"] += 1
        _advance_to_next_freq()

    def _finish_ear():
        ear = _state["ear"]
        if ear == "left":
            _begin_right()
        else:
            _show_results()

    def _stop_test():
        _cancel_timer()
        on_cancel()

    # ── results ───────────────────────────────────────────────────────────────

    def _show_results():
        _clear()
        frame.columnconfigure(0, weight=1)

        left_thresholds: dict[int, FrequencyThreshold] = _state["left"]
        right_thresholds: dict[int, FrequencyThreshold] = _state["right"]
        asymmetric = detect_asymmetric_frequencies(left_thresholds, right_thresholds)

        ttk.Label(frame, text="Hearing Test Results", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        # ── canvas bar chart ──
        canvas_w, canvas_h = 500, 160
        canvas = _draw_threshold_chart(
            ttk, frame,
            left=left_thresholds,
            right=right_thresholds,
            width=canvas_w,
            height=canvas_h,
        )
        canvas.grid(row=1, column=0, sticky="w", pady=(0, 12))

        # ── summary text ──
        n_determined = sum(
            1 for t in {**left_thresholds, **right_thresholds}.values() if t.determined
        )
        n_total = len(left_thresholds) + len(right_thresholds)
        summary_parts = [f"Thresholds determined: {n_determined} / {n_total}"]

        if asymmetric:
            freq_labels = ", ".join(_FREQ_LABELS.get(f, str(f)) for f in asymmetric)
            summary_parts.append(
                f"Large L/R difference (>{ASYMMETRY_WARNING_DB:.0f} dB) at: {freq_labels}. "
                "Consider consulting an audiologist."
            )

        # Estimate average compensation
        from ...hearing_test import compute_compensation_curve
        import numpy as np
        from ...signals import geometric_log_grid

        profile_for_preview = HearingProfile(
            left=left_thresholds,
            right=right_thresholds,
            tested_at=datetime.now(timezone.utc).isoformat(),
            asymmetric_freqs=asymmetric,
        )
        grid = geometric_log_grid(500.0, 8000.0, 48)
        comp = compute_compensation_curve(profile_for_preview, grid)
        avg_boost = float(np.mean(comp[comp > 0])) if np.any(comp > 0) else 0.0
        max_boost = float(np.max(comp))
        if max_boost > 0:
            summary_parts.append(
                f"EQ compensation: avg +{avg_boost:.1f} dB, max +{max_boost:.1f} dB "
                f"(half-gain rule, capped at {MAX_COMPENSATION_DB:.0f} dB)."
            )
        else:
            summary_parts.append("No EQ compensation needed — thresholds are at or below the normal reference.")

        for i, txt in enumerate(summary_parts):
            ttk.Label(frame, text=txt, wraplength=560, justify="left").grid(
                row=2 + i, column=0, sticky="w", pady=2
            )

        row_offset = 2 + len(summary_parts) + 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row_offset, column=0, sticky="w", pady=(8, 0))

        def _save_and_apply():
            profile = HearingProfile(
                left=left_thresholds,
                right=right_thresholds,
                tested_at=datetime.now(timezone.utc).isoformat(),
                asymmetric_freqs=asymmetric,
            )
            save_hearing_profile(profile)
            on_complete(profile)

        def _save_only():
            profile = HearingProfile(
                left=left_thresholds,
                right=right_thresholds,
                tested_at=datetime.now(timezone.utc).isoformat(),
                asymmetric_freqs=asymmetric,
            )
            save_hearing_profile(profile)
            on_cancel()

        ttk.Button(btn_frame, text="Save & Use for EQ", command=_save_and_apply, style="Accent.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btn_frame, text="Save Without Applying", command=_save_only).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btn_frame, text="Discard", command=on_cancel).grid(row=0, column=2)

    # ── kick off ──────────────────────────────────────────────────────────────
    _show_intro()


def _draw_threshold_chart(ttk, frame, *, left, right, width=500, height=160):
    """
    Draw a simple canvas bar chart of L/R thresholds per frequency.
    Returns the Canvas widget.
    """
    import tkinter as tk

    canvas = tk.Canvas(frame, width=width, height=height, bg="#f8f8f8", highlightthickness=1, highlightbackground="#cccccc")

    margin_l, margin_r, margin_t, margin_b = 44, 12, 16, 28
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    freqs = TEST_FREQUENCIES
    n = len(freqs)
    bar_group_w = plot_w / n
    bar_w = bar_group_w * 0.3

    # dBFS range for display
    y_min, y_max = -70.0, -5.0
    y_range = y_max - y_min

    def _y(level_dbfs: float) -> float:
        frac = (level_dbfs - y_min) / y_range
        return float(margin_t + plot_h * (1.0 - frac))

    # Axes
    canvas.create_line(margin_l, margin_t, margin_l, margin_t + plot_h, fill="#888888")
    canvas.create_line(margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h, fill="#888888")

    # Y gridlines and labels at -70, -55, -40, -25, -10 dBFS
    for db in (-70, -55, -40, -25, -10):
        y = _y(float(db))
        canvas.create_line(margin_l, y, margin_l + plot_w, y, fill="#dddddd", dash=(2, 3))
        canvas.create_text(margin_l - 3, y, text=str(db), anchor="e", font=("TkDefaultFont", 7), fill="#666666")

    normal_ref_avg = sum(NORMAL_HEARING_REFERENCE.get(f, -50.0) for f in freqs) / len(freqs)
    ref_y = _y(normal_ref_avg)
    canvas.create_line(margin_l, ref_y, margin_l + plot_w, ref_y, fill="#4488cc", dash=(4, 3), width=1)
    canvas.create_text(margin_l + plot_w, ref_y - 3, text="ref", anchor="e", font=("TkDefaultFont", 7), fill="#4488cc")

    for i, freq_hz in enumerate(freqs):
        x_center = margin_l + (i + 0.5) * bar_group_w

        # Frequency label
        canvas.create_text(
            x_center, margin_t + plot_h + 10,
            text=_FREQ_LABELS.get(freq_hz, str(freq_hz)).replace(" Hz", "").replace(" kHz", "k"),
            font=("TkDefaultFont", 7), fill="#444444"
        )

        for side, color, offset in (("left", "#2266cc", -bar_w * 0.55), ("right", "#cc4422", bar_w * 0.55)):
            data = left if side == "left" else right
            t = data.get(freq_hz)
            if t is None or not t.determined or t.level_dbfs is None:
                continue
            level = float(t.level_dbfs)
            y_bar = _y(level)
            y_bottom = _y(y_min)
            x0 = x_center + offset - bar_w / 2
            x1 = x_center + offset + bar_w / 2
            canvas.create_rectangle(x0, y_bar, x1, y_bottom, fill=color, outline="")

    # Legend
    canvas.create_rectangle(margin_l, height - 10, margin_l + 8, height - 4, fill="#2266cc", outline="")
    canvas.create_text(margin_l + 11, height - 7, text="L", anchor="w", font=("TkDefaultFont", 7), fill="#2266cc")
    canvas.create_rectangle(margin_l + 22, height - 10, margin_l + 30, height - 4, fill="#cc4422", outline="")
    canvas.create_text(margin_l + 33, height - 7, text="R", anchor="w", font=("TkDefaultFont", 7), fill="#cc4422")

    return canvas
