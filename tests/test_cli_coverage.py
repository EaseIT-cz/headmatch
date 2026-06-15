"""Targeted coverage tests for headmatch.cli line-by-line branches.

Every test drives the CLI via cli.main(argv) (or a helper function directly),
mocking all heavy/hardware/pipeline/network dependencies so the suite stays
fast and deterministic. New tests only; existing test files are untouched.
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from headmatch import cli
from headmatch.contracts import FrontendConfig


@pytest.fixture(autouse=True)
def patch_config_and_sweep(monkeypatch, tmp_path):
    """Isolate config IO and the SweepSpec so dispatch never touches real state."""

    class DummySweepSpec:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr("headmatch.signals.SweepSpec", DummySweepSpec)
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), tmp_path / "config.json", False),
    )
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_a, **_k: None)


# ── helpers ───────────────────────────────────────────────────────────────


def _make_hearing_profile(*, unreliable_ears=None, asymmetric_freqs=None):
    from headmatch.hearing_test import (
        NORMAL_HEARING_REFERENCE,
        TEST_FREQUENCIES,
        FrequencyThreshold,
        HearingProfile,
    )

    side = {
        f: FrequencyThreshold(
            freq_hz=f,
            level_dbfs=NORMAL_HEARING_REFERENCE[f],
            ascending_runs=3,
            determined=True,
        )
        for f in TEST_FREQUENCIES
    }
    return HearingProfile(
        left=dict(side),
        right=dict(side),
        tested_at="2026-01-01T00:00:00+00:00",
        asymmetric_freqs=asymmetric_freqs or [],
        unreliable_ears=unreliable_ears or [],
    )


class FakeBackend:
    def play_tone(self, *a, **kw):
        pass


# ── _run_summary_path (line 354) ─────────────────────────────────────────────


def test_run_summary_path_returns_none_for_non_positive_iterations():
    # cmd in {start, iterate}, independent mode, iterations not a positive int
    args = type("A", (), {"out_dir": "/tmp/out", "iteration_mode": "independent", "iterations": 0})()
    assert cli._run_summary_path("start", args) is None


# ── print_clipping_summary preamp fallback (line 416) ────────────────────────


def test_print_clipping_summary_falls_back_to_total_preamp_db(capsys):
    summary = type(
        "S",
        (),
        {
            "eq_clipping_assessment": {
                "will_clip": False,
                "total_preamp_db": -3.5,
                "left_peak_boost_db": 1.0,
                "right_peak_boost_db": 1.0,
                "headroom_loss_db": 0.0,
            }
        },
    )()
    cli.print_clipping_summary(summary)
    out = capsys.readouterr().out
    assert "Preamp recommendation: -3.5 dB" in out


# ── fit next-steps with corrupt summary (lines 461-462) ──────────────────────


def test_print_next_steps_fit_with_unreadable_summary(capsys, tmp_path):
    out_dir = tmp_path / "fit"
    out_dir.mkdir()
    (out_dir / "run_summary.json").write_text("{not valid json", encoding="utf-8")
    # _run_summary_path("fit") points at run_summary.json which exists but is
    # corrupt -> summary becomes None and clipping summary is skipped.
    cli.print_next_steps("fit", type("A", (), {"out_dir": str(out_dir)})())
    out = capsys.readouterr().out
    assert "Done. Review outputs in" in out
    assert "Preamp recommendation" not in out


# ── format_user_error default (line 505) ─────────────────────────────────────


def test_format_user_error_default_passthrough():
    assert cli.format_user_error("measure", ValueError("boom")) == "boom"


# ── render-sweep dispatch (line 559) ─────────────────────────────────────────


def test_render_sweep_dispatches(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr(
        "headmatch.measure.render_sweep_file",
        lambda spec, out: calls.update({"out": out}),
    )
    cli.main(["render-sweep", "--out", str(tmp_path / "sweep.wav")])
    assert calls["out"] == str(tmp_path / "sweep.wav")


# ── doctor shortcut tips (lines 582-583, 585) ────────────────────────────────


def _patch_doctor_report(monkeypatch):
    monkeypatch.setattr(
        "headmatch.measure.collect_doctor_checks", lambda path, config: []
    )
    monkeypatch.setattr(
        "headmatch.measure.format_doctor_report",
        lambda checks, config_path: "HeadMatch doctor report",
    )


def test_doctor_suggests_creating_shortcut_when_gui_present(monkeypatch, capsys):
    _patch_doctor_report(monkeypatch)
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: "/usr/bin/headmatch-gui")
    monkeypatch.setattr("headmatch.desktop.shortcut_exists", lambda: False)
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "headmatch create-shortcut" in out
    assert "/usr/bin/headmatch-gui" in out


def test_doctor_reports_installed_shortcut(monkeypatch, capsys):
    _patch_doctor_report(monkeypatch)
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: "/usr/bin/headmatch-gui")
    monkeypatch.setattr("headmatch.desktop.shortcut_exists", lambda: True)
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "Desktop shortcut: installed" in out


# ── hearing-test branches (616, 623-625, 636-637, 640-641) ───────────────────


def _patch_hearing_test_backend(monkeypatch, profile):
    monkeypatch.setattr("headmatch.audio_backend.get_audio_backend", lambda: FakeBackend())
    monkeypatch.setattr("headmatch.hearing_test.run_cli_hearing_test", lambda *a, **kw: profile)
    monkeypatch.setattr(
        "headmatch.hearing_test.save_hearing_profile",
        lambda p: Path("/tmp/hearing_profile.json"),
    )


def test_hearing_test_extended_hf_prints_air_band_note(monkeypatch, capsys):
    profile = _make_hearing_profile()
    _patch_hearing_test_backend(monkeypatch, profile)
    cli.main(["hearing-test", "--extended-hf"])
    out = capsys.readouterr().out
    assert "Extended high frequencies" in out


def test_hearing_test_json_output(monkeypatch, capsys):
    profile = _make_hearing_profile()
    _patch_hearing_test_backend(monkeypatch, profile)
    monkeypatch.setattr(
        "headmatch.hearing_test.compute_hearing_summary",
        lambda p: {"who_grade": "normal", "better_ear_pta_db": 5.0},
    )
    cli.main(["hearing-test", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hearing_summary"]["who_grade"] == "normal"


def test_hearing_test_prints_who_grade_and_warnings(monkeypatch, capsys):
    profile = _make_hearing_profile(unreliable_ears=["left"], asymmetric_freqs=[4000])
    _patch_hearing_test_backend(monkeypatch, profile)
    monkeypatch.setattr(
        "headmatch.hearing_test.compute_hearing_summary",
        lambda p: {"who_grade": "mild", "better_ear_pta_db": 28.4},
    )
    cli.main(["hearing-test"])
    out = capsys.readouterr().out
    assert "Estimated hearing: mild" in out
    assert "high false-positive rate on the left ear" in out
    assert "large L/R difference at 4000 Hz" in out


# ── hearing-fit branches (657, 672-673) ──────────────────────────────────────


def test_hearing_fit_exits_when_no_profile(monkeypatch, tmp_path):
    monkeypatch.setattr("headmatch.hearing_test.load_hearing_profile", lambda: None)
    monkeypatch.setattr(
        "headmatch.hearing_test.hearing_profile_path",
        lambda: tmp_path / "hearing_profile.json",
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(["hearing-fit", "--out-dir", str(tmp_path)])
    assert exc.value.code == 2


def test_hearing_fit_json_swallows_read_error(monkeypatch, capsys, tmp_path):
    profile = _make_hearing_profile()
    monkeypatch.setattr("headmatch.hearing_test.load_hearing_profile", lambda: profile)
    # run_hearing_fit does not write the report -> reading it raises -> except: pass
    monkeypatch.setattr("headmatch.pipeline.run_hearing_fit", lambda *a, **kw: {})
    cli.main(["hearing-fit", "--out-dir", str(tmp_path / "fit"), "--json"])
    out = capsys.readouterr().out
    # No JSON printed; next-steps message still runs.
    assert "Hearing fit complete" in out


# ── fit --with-hearing-compensation no profile (lines 677-680) ───────────────


def test_fit_with_hearing_compensation_exits_without_profile(monkeypatch, tmp_path):
    monkeypatch.setattr("headmatch.hearing_test.load_hearing_profile", lambda: None)
    monkeypatch.setattr(
        "headmatch.hearing_test.hearing_profile_path",
        lambda: tmp_path / "hearing_profile.json",
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "fit",
                "--recording",
                str(tmp_path / "r.wav"),
                "--out-dir",
                str(tmp_path / "fit"),
                "--with-hearing-compensation",
            ]
        )
    assert exc.value.code == 2


# ── fit --json swallows read error (lines 687-688) ───────────────────────────


def test_fit_json_swallows_missing_summary(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "headmatch.pipeline.process_single_measurement", lambda *a, **k: None
    )
    # No run_summary.json written -> read raises -> except: pass, returns early.
    cli.main(
        [
            "fit",
            "--recording",
            str(tmp_path / "r.wav"),
            "--out-dir",
            str(tmp_path / "fit"),
            "--json",
        ]
    )
    assert capsys.readouterr().out == ""


# ── search-headphone empty + truncated (lines 693, 702) ──────────────────────


def test_search_headphone_no_results(monkeypatch, capsys):
    monkeypatch.setattr("headmatch.headphone_db.search_headphone", lambda q: [])
    cli.main(["search-headphone", "nope"])
    out = capsys.readouterr().out
    assert "No matches for 'nope'" in out


def test_search_headphone_truncates_over_25(monkeypatch, capsys):
    from headmatch.headphone_db import HeadphoneEntry

    entries = [
        HeadphoneEntry(
            name=f"HP {i}",
            source="src",
            form_factor="over-ear",
            csv_path=f"results/src/over-ear/HP {i}/HP {i}.csv",
        )
        for i in range(30)
    ]
    monkeypatch.setattr("headmatch.headphone_db.search_headphone", lambda q: entries)
    cli.main(["search-headphone", "HP"])
    out = capsys.readouterr().out
    assert "Found 30 matches" in out
    assert "... and 5 more" in out


# ── batch-fit (lines 738-757) ────────────────────────────────────────────────


def test_batch_fit_reports_success_and_failure(monkeypatch, capsys, tmp_path):
    ok = types.SimpleNamespace(
        success=True,
        label="A",
        predicted_left_rms_error_db=1.0,
        predicted_right_rms_error_db=1.2,
        confidence_label="high",
        error=None,
    )
    bad = types.SimpleNamespace(success=False, label="B", error="boom")

    def fake_run_batch_fit(manifest, spec, *, max_filters, filter_budget, on_progress):
        on_progress(1, 2, "A")
        on_progress(2, 2, "B")
        return [ok, bad]

    monkeypatch.setattr("headmatch.batch.run_batch_fit", fake_run_batch_fit)
    cli.main(["batch-fit", "--manifest", str(tmp_path / "m.json")])
    out = capsys.readouterr().out
    assert "Running batch fit from" in out
    assert "[1/2] A ..." in out
    assert "Batch complete: 1 succeeded, 1 failed out of 2." in out
    assert "A: L=1.00 R=1.20" in out
    assert "B: boom" in out


# ── batch-template (lines 758-762) ───────────────────────────────────────────


def test_batch_template_writes_file(monkeypatch, capsys, tmp_path):
    out_path = tmp_path / "batch_manifest.json"
    monkeypatch.setattr(
        "headmatch.batch.generate_manifest_template",
        lambda out, num_entries: Path(out),
    )
    cli.main(["batch-template", "--out", str(out_path), "--entries", "2"])
    out = capsys.readouterr().out
    assert f"Template written to {out_path}" in out
    assert "Edit the entries array" in out


# ── history (lines 763-774) ──────────────────────────────────────────────────


def test_history_no_runs(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("headmatch.history.load_recent_runs", lambda root, limit: [])
    cli.main(["history", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "No run_summary.json files found" in out


def test_history_lists_runs(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "headmatch.history.load_recent_runs", lambda root, limit: ["e1", "e2"]
    )
    monkeypatch.setattr(
        "headmatch.history.format_run_entry", lambda entry, index: f"#{index} {entry}"
    )
    cli.main(["history", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Recent runs under" in out
    assert "#1 e1" in out
    assert "#2 e2" in out


# ── compare-runs (lines 775-785) ─────────────────────────────────────────────


def test_compare_runs_needs_two(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("headmatch.history.load_recent_runs", lambda root, limit: ["only"])
    cli.main(["compare-runs", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Need at least 2 runs" in out


def test_compare_runs_cannot_build(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "headmatch.history.load_recent_runs", lambda root, limit: ["a", "b"]
    )
    monkeypatch.setattr("headmatch.history.build_run_comparison", lambda runs: None)
    cli.main(["compare-runs", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Could not build comparison." in out


def test_compare_runs_renders_table(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "headmatch.history.load_recent_runs", lambda root, limit: ["a", "b"]
    )
    monkeypatch.setattr(
        "headmatch.history.build_run_comparison", lambda runs: "COMP"
    )
    monkeypatch.setattr(
        "headmatch.history.format_comparison_table", lambda comparison: "TABLE-OUT"
    )
    cli.main(["compare-runs", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "TABLE-OUT" in out


# ── compare-ab (lines 786-798) ───────────────────────────────────────────────


def test_compare_ab_exports_presets(monkeypatch, capsys, tmp_path):
    export = types.SimpleNamespace(
        output_dir=str(tmp_path / "ab"),
        preset_a_apo=Path("A_equalizer_apo.txt"),
        preset_b_apo=Path("B_equalizer_apo.txt"),
        preset_a_cdsp=Path("A_camilladsp_full.yaml"),
        preset_b_cdsp=Path("B_camilladsp_full.yaml"),
        comparison_json=Path("comparison.json"),
    )
    monkeypatch.setattr(
        "headmatch.ab_compare.build_comparison_pair",
        lambda a, b, *, label_a, label_b: "PAIR",
    )
    monkeypatch.setattr(
        "headmatch.ab_compare.format_comparison_table", lambda pair: "AB-TABLE"
    )
    monkeypatch.setattr(
        "headmatch.ab_compare.export_ab_comparison", lambda pair, out_dir: export
    )
    cli.main(
        [
            "compare-ab",
            "--run-a",
            str(tmp_path / "a"),
            "--run-b",
            str(tmp_path / "b"),
            "--out-dir",
            str(tmp_path / "ab"),
        ]
    )
    out = capsys.readouterr().out
    assert "AB-TABLE" in out
    assert "Presets exported to" in out
    assert "A_equalizer_apo.txt" in out
    assert "comparison.json" in out


# ── iterate (lines 799-810) ──────────────────────────────────────────────────


def test_iterate_dispatches(monkeypatch, capsys, tmp_path):
    calls = {}
    monkeypatch.setattr(
        "headmatch.pipeline.iterative_measure_and_fit",
        lambda **kw: calls.update(kw),
    )
    cli.main(["iterate", "--out-dir", str(tmp_path / "out")])
    assert calls["output_dir"] == str(tmp_path / "out")
    out = capsys.readouterr().out
    assert "Done. Review outputs in" in out


# ── ValueError handler (line 812) ────────────────────────────────────────────


def test_value_error_from_handler_exits_with_message(monkeypatch, capsys, tmp_path):
    def boom(*a, **k):
        raise ValueError("bad input")

    monkeypatch.setattr("headmatch.pipeline.build_clone_curve", boom)
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "clone-target",
                "--source-csv",
                "s.csv",
                "--target-csv",
                "t.csv",
                "--out",
                str(tmp_path / "out.csv"),
            ]
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Error: clone-target failed: bad input" in err


# ── save_config OSError swallowed (lines 817-818) ────────────────────────────


def test_save_config_oserror_is_swallowed(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "headmatch.measure.render_sweep_file", lambda spec, out: None
    )

    def raise_oserror(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("headmatch.cli.save_config", raise_oserror)
    # render-sweep is not in the skip set, so save_config runs; OSError is caught.
    cli.main(["render-sweep", "--out", str(tmp_path / "sweep.wav")])
    # No exception propagates; render-sweep has no next-steps output.
    assert "Traceback" not in capsys.readouterr().out
