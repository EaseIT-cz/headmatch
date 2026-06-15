"""Coverage tests for headmatch.measure — error/edge branches."""
from __future__ import annotations

from pathlib import Path

import pytest

from headmatch.contracts import FrontendConfig
from headmatch.measure import (
    DoctorCheck,
    OfflineMeasurementPlan,
    PipeWireTarget,
    _saved_target_matches_discovery,
    collect_doctor_checks,
    format_doctor_report,
    prepare_offline_measurement,
    render_sweep_file,
    require_executable,
    run_pipewire_measurement,
)
from headmatch.signals import SweepSpec


class TestRequireExecutable:
    def test_missing_raises(self, monkeypatch):
        monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: None)
        with pytest.raises(RuntimeError, match="Required executable not found"):
            require_executable("definitely-not-a-real-binary")

    def test_present_does_not_raise(self, monkeypatch):
        monkeypatch.setattr("headmatch.measure.shutil.which", lambda name: "/usr/bin/x")
        require_executable("x")


class TestRenderAndPrepareOffline:
    def test_render_sweep_file(self, tmp_path):
        spec = SweepSpec(sample_rate=48000, duration_s=0.2,
                         pre_silence_s=0.05, post_silence_s=0.05)
        out = render_sweep_file(spec, tmp_path / "sweep.wav")
        assert out.exists()

    def test_prepare_offline_measurement_writes_files(self, tmp_path):
        spec = SweepSpec(sample_rate=48000, duration_s=0.2,
                         pre_silence_s=0.05, post_silence_s=0.05)
        plan = OfflineMeasurementPlan(
            sweep_wav=tmp_path / "nested" / "sweep.wav",
            metadata_json=tmp_path / "meta" / "plan.json",
            notes="hello",
        )
        payload = prepare_offline_measurement(spec, plan)
        assert plan.sweep_wav.exists()
        assert plan.metadata_json.exists()
        assert payload["mode"] == "offline"
        assert payload["notes"] == "hello"
        assert payload["sweep"]["sample_rate"] == 48000
        assert payload["files"]["sweep_wav"] == str(plan.sweep_wav)


class TestRunPipewireMeasurement:
    def test_delegates_to_backend(self, monkeypatch, tmp_path):
        spec = SweepSpec()
        sentinel_path = tmp_path / "recording.wav"

        class FakeBackend:
            def play_and_record(self, spec_, paths_, device_):
                return sentinel_path

        monkeypatch.setattr(
            "headmatch.measure.get_audio_backend", lambda: FakeBackend()
        )
        result = run_pipewire_measurement(spec, paths="P", device="D")
        assert result == sentinel_path


class TestSavedTargetMatches:
    def test_empty_saved_returns_false(self):
        assert _saved_target_matches_discovery("   ", "playback", []) is False


class TestCollectDoctorChecksDiscoveryNone:
    def test_discovery_failure_with_saved_targets(self, monkeypatch, tmp_path):
        # Backend collect_doctor_checks returns nothing extra; force discovery
        # to raise RuntimeError so `discovered is None` branches run (172, 191).
        class FakeBackend:
            def collect_doctor_checks(self):
                return []

        monkeypatch.setattr(
            "headmatch.measure.get_audio_backend", lambda: FakeBackend()
        )

        def _boom():
            raise RuntimeError("no audio")

        monkeypatch.setattr("headmatch.measure.list_pipewire_targets", _boom)

        config = FrontendConfig(
            pipewire_output_target="usb-dac",
            pipewire_input_target="usb-mic",
        )
        checks = collect_doctor_checks(tmp_path / "config.json", config)
        by_name = {c.name: c for c in checks}
        assert by_name["saved output target"].ok is True
        assert by_name["saved output target"].detail == "Configured: usb-dac"
        assert by_name["saved input target"].ok is True
        assert by_name["saved input target"].detail == "Configured: usb-mic"


class TestFormatDoctorReportNoActions:
    def test_no_actions_shows_default_next_step(self, tmp_path):
        text = format_doctor_report(
            [DoctorCheck(name="config file", ok=True, detail="Using config.json")],
            config_path=tmp_path / "config.json",
        )
        assert "Suggested next step:" in text
        assert "headmatch list-targets" in text
