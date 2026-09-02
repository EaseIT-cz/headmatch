from __future__ import annotations

from .common import (
    add_entry_row,
    add_picker_row,
    SECTION_PAD,
    BODY_WRAP,
    DETAIL_WRAP,
)

__all__ = ['render_room_correction', 'ROOM_STEPS']


# Speaker/room correction is a different job from headphone correction, and the
# steps differ enough that reusing OFFLINE_STEPS would mislead: the sweep is
# played through speakers into the room, the microphone wants calibration, and
# averaging several listening positions is normal rather than exotic.
ROOM_STEPS: tuple[str, ...] = (
    "Write the room sweep package below, then play room_sweep.wav through your speakers.",
    "Record it at the listening position with a measurement microphone.",
    "Measure a second position too if you can — averaging two positions avoids correcting for one chair.",
    "Load the recording(s) here to fit correction EQ below the transition frequency.",
)


def render_room_correction(ttk, frame, *, variables, on_prepare, on_fit) -> None:
    ttk.Label(frame, text="Room correction", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        frame,
        text=(
            "Correct speaker-in-room response at low frequencies, where the room dominates. "
            "This is for speakers, not headphones — measure with a microphone at the listening position."
        ),
        wraplength=BODY_WRAP,
        justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(8, 12))

    steps = ttk.LabelFrame(frame, text="What happens", padding=SECTION_PAD)
    steps.grid(row=2, column=0, sticky="ew")
    for idx, step in enumerate(ROOM_STEPS):
        ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=DETAIL_WRAP, justify="left").grid(
            row=idx, column=0, sticky="w", pady=2
        )

    prep = ttk.LabelFrame(frame, text="Step A — prepare the room sweep package", padding=SECTION_PAD)
    prep.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    prep.columnconfigure(1, weight=1)
    add_picker_row(
        ttk, prep, 0, "Package folder", variables.room_output_var,
        button_text="Browse…", command=variables.choose_room_output_dir,
    )
    add_picker_row(
        ttk, prep, 1, "Mic calibration (optional)", variables.room_mic_cal_var,
        button_text="Browse…", command=variables.choose_room_mic_cal,
    )
    add_entry_row(ttk, prep, 2, "Transition frequency (Hz)", variables.room_cutoff_hz_var)
    ttk.Checkbutton(
        prep,
        text="Prepare for two listening positions",
        variable=variables.room_two_positions_var,
        onvalue="1",
        offvalue="0",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
    ttk.Button(prep, text="Write room sweep package", command=on_prepare).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )

    fit = ttk.LabelFrame(frame, text="Step B — fit correction from the recording", padding=SECTION_PAD)
    fit.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    fit.columnconfigure(1, weight=1)
    add_picker_row(
        ttk, fit, 0, "Recorded WAV", variables.room_recording_var,
        button_text="Browse…", command=variables.choose_room_recording,
    )
    add_picker_row(
        ttk, fit, 1, "Second position (optional)", variables.room_recording_two_var,
        button_text="Browse…", command=variables.choose_room_recording_two,
    )
    add_picker_row(
        ttk, fit, 2, "Room target CSV (optional)", variables.room_target_csv_var,
        button_text="Browse…", command=variables.choose_room_target_csv,
    )
    add_picker_row(
        ttk, fit, 3, "Fit output folder", variables.room_fit_output_var,
        button_text="Browse…", command=variables.choose_room_fit_output_dir,
    )
    add_entry_row(ttk, fit, 4, "Max boost (dB)", variables.room_max_boost_db_var)
    ttk.Button(fit, text="Fit room correction", command=on_fit).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )
