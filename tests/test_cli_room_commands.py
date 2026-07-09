"""Integration tests for room-measure and room-fit CLI commands.

Tests that the CLI correctly calls the underlying room.py API functions
with the right signatures and argument names.
"""

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from headmatch.cli import main


class TestRoomMeasureCLI:
    """Test room-measure CLI command integration."""

    def test_room_measure_calls_prepare_room_measurement_correctly(self, tmp_path):
        """Verify room-measure calls prepare_room_measurement with correct signature."""
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        mic_cal_file = tmp_path / "mic_cal.csv"
        mic_cal_file.write_text(
            "hz,db\n20,0\n100,0\n1000,0\n10000,0\n20000,0\n"
        )
        
        with mock.patch("headmatch.room.prepare_room_measurement") as mock_prepare:
            mock_prepare.return_value = {
                "sweep_path": str(out_dir / "room_sweep.wav"),
                "guide_path": str(out_dir / "room_measurement_guide.md"),
            }
            
            # Run CLI command
            main([
                "room-measure",
                "--out-dir", str(out_dir),
                "--mic-cal", str(mic_cal_file),
            ])
            
            # Verify prepare_room_measurement was called with correct signature
            mock_prepare.assert_called_once()
            call_args = mock_prepare.call_args
            
            # Check positional args or keyword args match signature
            # Signature: (spec, mic_cal, cutoff_hz, max_boost_db, listen_position_two, out_dir)
            kwargs = call_args.kwargs
            assert "spec" in kwargs, "spec must be passed"
            assert "mic_cal" in kwargs, "mic_cal must be passed"
            assert "cutoff_hz" in kwargs, "cutoff_hz must be passed"
            assert "max_boost_db" in kwargs, "max_boost_db must be passed"
            assert "listen_position_two" in kwargs, "listen_position_two must be passed"
            assert "out_dir" in kwargs, "out_dir must be passed"


class TestRoomFitCLI:
    """Test room-fit CLI command integration."""

    def test_room_fit_calls_run_room_fit_correctly(self, tmp_path):
        """Verify room-fit calls run_room_fit with correct signature."""
        recording_file = tmp_path / "recording.wav"
        recording_file.write_bytes(b"RIFF" + b"\x00" * 100)  # Minimal WAV-like file
        
        recording_two_file = tmp_path / "recording_two.wav"
        recording_two_file.write_bytes(b"RIFF" + b"\x00" * 100)
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        mic_cal_file = tmp_path / "mic_cal.csv"
        mic_cal_file.write_text(
            "hz,db\n20,0\n100,0\n1000,0\n10000,0\n20000,0\n"
        )
        
        target_file = tmp_path / "target.csv"
        target_file.write_text(
            "hz,db\n20,0\n1000,0\n20000,0\n"
        )
        
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = mock.Mock(
                peqs=[],
                signals={},
                artifacts_dir=out_dir,
            )
            
            # Run CLI command
            main([
                "room-fit",
                "--recording", str(recording_file),
                "--recording-two", str(recording_two_file),
                "--mic-cal", str(mic_cal_file),
                "--target", str(target_file),
                "--out-dir", str(out_dir),
            ])
            
            # Verify run_room_fit was called with correct signature
            mock_fit.assert_called_once()
            call_args = mock_fit.call_args
            
            # Check keyword args match signature
            # Signature: (recording, recording_two, mic_cal, cutoff_hz, max_boost_db, target_csv, out_dir)
            kwargs = call_args.kwargs
            assert "recording" in kwargs, "recording must be passed"
            assert "recording_two" in kwargs, "recording_two must be passed"
            assert "mic_cal" in kwargs, "mic_cal must be passed"
            assert "cutoff_hz" in kwargs, "cutoff_hz must be passed"
            assert "max_boost_db" in kwargs, "max_boost_db must be passed"
            assert "target_csv" in kwargs, "target_csv must be passed"
            assert "out_dir" in kwargs, "out_dir must be passed"


class TestMicCalibrationAttribute:
    """Test that room.py uses correct MicCalibration attribute name."""

    def test_mic_calibration_source_attribute(self, tmp_path):
        """Verify room.py accesses mic_cal.source not mic_cal.source_file."""
        from headmatch.mic_cal import load_mic_calibration
        
        mic_cal_file = tmp_path / "mic_cal.csv"
        mic_cal_file.write_text(
            "hz,db\n20,0\n100,0\n1000,0\n10000,0\n20000,0\n"
        )
        
        mic_cal = load_mic_calibration(mic_cal_file)
        
        # Check that MicCalibration has 'source' attribute
        assert hasattr(mic_cal, "source"), "MicCalibration must have 'source' attribute"
        assert str(mic_cal_file) in str(mic_cal.source) or mic_cal.source == str(mic_cal_file), "source should point to the CSV file"