from __future__ import annotations

from uuid import uuid4

from headmatch.contracts import FrontendConfig


def varied_config(*, suffix: str | None = None) -> tuple[str, FrontendConfig]:
    suffix = suffix or uuid4().hex
    sample_rate = 43100 + (int(suffix[:2], 16) % 2000)
    duration_s = 4.5 + ((int(suffix[2:4], 16) % 25) / 10)
    f_start_hz = 15.0 + (int(suffix[4:6], 16) % 35)
    f_end_hz = 17000.0 + (int(suffix[6:8], 16) % 5000)
    pre_silence_s = 0.1 + ((int(suffix[8:10], 16) % 6) / 10)
    post_silence_s = 0.6 + ((int(suffix[10:12], 16) % 8) / 10)
    amplitude = 0.1 + ((int(suffix[12:14], 16) % 8) / 100)
    max_filters = 4 + (int(suffix[14:16], 16) % 8)
    start_iterations = 2 + (int(suffix[16:18], 16) % 6)
    iterate_iterations = 3 + (int(suffix[18:20], 16) % 6)
    return suffix, FrontendConfig(
        default_output_dir=f"out/{suffix}",
        preferred_target_csv=f"targets/{suffix}.csv",
        pipewire_output_target=f"playback-{suffix}",
        pipewire_input_target=f"capture-{suffix}",
        sample_rate=sample_rate,
        duration_s=duration_s,
        f_start_hz=f_start_hz,
        f_end_hz=f_end_hz,
        pre_silence_s=pre_silence_s,
        post_silence_s=post_silence_s,
        amplitude=amplitude,
        max_filters=max_filters,
        start_iterations=start_iterations,
        iterate_iterations=iterate_iterations,
    )
