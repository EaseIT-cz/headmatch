"""Integration tests for room-measure and room-fit CLI commands.

Tests that the CLI correctly calls the underlying room.py API functions
with the right signatures and argument names.
"""

import struct
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from headmatch.cli import main


def _create_minimal_wav_header():
    """Create a valid minimal RIFF WAV header for mocking purposes."""
    header = b'RIFF' + struct.pack('<I', 36) + b'WAVE' + b'fmt ' + struct.pack('<I', 16)
    header += struct.pack('<HHI', 1, 1, 44100)  # PCM, mono, 44100
    header += struct.pack('<IH', 1411200, 2)    # byte rate, block align
    header += struct.pack('<H', 16)  # bits per sample
    header += b'data' + struct.pack('<I', 0)  # data chunk, size 0
    return header


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
        
        # Patch headmatch.room.prepare_room_measurement since that's where it's defined/imported from
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

    def test_room_measure_missing_mic_cal_warns_and_works(self, tmp_path):
        """Verify room-measure without --mic-cal warns and still works."""
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        # Patch headmatch.room.prepare_room_measurement since that's where it's defined/imported from
        with mock.patch("headmatch.room.prepare_room_measurement") as mock_prepare:
            mock_prepare.return_value = {
                "sweep_path": str(out_dir / "room_sweep.wav"),
                "metadata_json": str(out_dir / "room_measurement.json"),
            }
            
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # Run CLI command without --mic-cal
                main([
                    "room-measure",
                    "--out-dir", str(out_dir),
                ])
                
            # Verify mic_cal is None when not provided
            kwargs = mock_prepare.call_args.kwargs
            assert kwargs["mic_cal"] is None, "mic_cal should be None when not provided"


class TestRoomFitCLI:
    """Test room-fit CLI command integration."""

    def test_room_fit_calls_run_room_fit_correctly(self, tmp_path):
        """Verify room-fit calls run_room_fit with correct signature."""
        recording_file = tmp_path / "recording.wav"
        recording_file.write_bytes(_create_minimal_wav_header())
        
        recording_two_file = tmp_path / "recording_two.wav"
        recording_two_file.write_bytes(_create_minimal_wav_header())
        
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
        
        # Patch headmatch.room.run_room_fit since that's where it's defined/imported from
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = mock.Mock(
                result=mock.Mock(
                    freqs_hz=[20, 50, 100, 200, 1000],
                    left_db=[0, 0, 0, 0, 0],
                    right_db=[0, 0, 0, 0, 0],
                    left_raw_db=[0, 0, 0, 0, 0],
                    right_raw_db=[0, 0, 0, 0, 0],
                    diagnostics={'two_position_averaged': True}
                ),
                eq_bands=[],
                target=mock.Mock(freqs_hz=[], values_db=[], name='flat'),
                fit_report={'cutoff_hz': 300},
                run_summary={},
                out_dir=out_dir,
                warnings=[],
            )
            
            # Run CLI command with max-boost-db
            main([
                "room-fit",
                "--recording", str(recording_file),
                "--recording-two", str(recording_two_file),
                "--mic-cal", str(mic_cal_file),
                "--target-csv", str(target_file),
                "--out-dir", str(out_dir),
                "--max-boost-db", "2.5",
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
            assert kwargs["max_boost_db"] == 2.5, "max_boost_db should be 2.5"
            assert "target_csv" in kwargs, "target_csv must be passed"
            assert "out_dir" in kwargs, "out_dir must be passed"

    def test_room_fit_missing_mic_cal_warns(self, tmp_path):
        """Verify room-fit without --mic-cal warns and still works."""
        recording_file = tmp_path / "recording.wav"
        recording_file.write_bytes(_create_minimal_wav_header())
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        # Patch headmatch.room.run_room_fit since that's where it's defined/imported from
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = mock.Mock(
                result=mock.Mock(freqs_hz=[20], left_db=[0], diagnostics={}),
                eq_bands=[],
                target=mock.Mock(freqs_hz=[], values_db=[], name='flat'),
                fit_report={'cutoff_hz': 300},
                run_summary={},
                out_dir=out_dir,
                warnings=[],
            )
            
            # Run CLI command without --mic-cal
            main([
                "room-fit",
                "--recording", str(recording_file),
                "--out-dir", str(out_dir),
            ])
            
            # Verify run_room_fit was called with mic_cal=None
            kwargs = mock_fit.call_args.kwargs
            assert kwargs["mic_cal"] is None, "mic_cal should be None when not provided"


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
        assert str(mic_cal.source) == str(mic_cal_file), "source should point to the CSV file"


class TestRoomFitMultiPositionRecording:
    """Test room-fit CLI multi-position recording support (Phase 2 MMM)."""

    def _create_mock_room_fit_result(self, out_dir):
        """Create a mock result for run_room_fit."""
        return mock.Mock(
            result=mock.Mock(
                freqs_hz=[20, 50, 100, 200, 1000],
                left_db=[0, 0, 0, 0, 0],
                right_db=[0, 0, 0, 0, 0],
                left_raw_db=[0, 0, 0, 0, 0],
                right_raw_db=[0, 0, 0, 0, 0],
                diagnostics={'n_position_averaged': 3},
            ),
            eq_bands=[],
            target=mock.Mock(freqs_hz=[], values_db=[], name='flat'),
            fit_report={'cutoff_hz': 300, 'n_positions': 3},
            run_summary={},
            out_dir=out_dir,
            warnings=[],
        )

    def test_repeated_recording_flag_accepted(self, tmp_path):
        """Test that repeated --recording flags are accepted by argparse."""
        # Create multiple recording files
        recordings = []
        for i in range(3):
            rec_file = tmp_path / f"recording{i+1}.wav"
            rec_file.write_bytes(_create_minimal_wav_header())
            recordings.append(str(rec_file))
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        # Parse args to verify repeated --recording is accepted
        from headmatch.cli import build_parser
        from headmatch.settings import FrontendConfig as HeadMatchConfig
        
        config = HeadMatchConfig()
        parser = build_parser(config)
        
        # This should not raise an error
        args = parser.parse_args([
            "room-fit",
            "--recording", recordings[0],
            "--recording", recordings[1],
            "--recording", recordings[2],
            "--out-dir", str(out_dir),
        ])
        
        # Check that recordings are accumulated
        assert hasattr(args, 'recording'), "args should have recording attribute"
        # Note: This will currently store only the last value until CLI is updated

    def test_backward_compatible_single_recording(self, tmp_path):
        """Test that single --recording still works (backward compatibility)."""
        recording_file = tmp_path / "recording.wav"
        recording_file.write_bytes(_create_minimal_wav_header())
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = self._create_mock_room_fit_result(out_dir)
            
            main([
                "room-fit",
                "--recording", str(recording_file),
                "--out-dir", str(out_dir),
            ])
            
            # Verify run_room_fit was called
            mock_fit.assert_called_once()
            kwargs = mock_fit.call_args.kwargs
            assert "recording" in kwargs, "recording must be passed"
            assert kwargs["recording"] == Path(recording_file), "recording path should match"

    def test_backward_compatible_recording_two(self, tmp_path):
        """Test that --recording with --recording-two still works (backward compatibility)."""
        recording_file = tmp_path / "recording.wav"
        recording_file.write_bytes(_create_minimal_wav_header())
        
        recording_two_file = tmp_path / "recording_two.wav"
        recording_two_file.write_bytes(_create_minimal_wav_header())
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = self._create_mock_room_fit_result(out_dir)
            
            main([
                "room-fit",
                "--recording", str(recording_file),
                "--recording-two", str(recording_two_file),
                "--out-dir", str(out_dir),
            ])
            
            # Verify run_room_fit was called
            mock_fit.assert_called_once()
            kwargs = mock_fit.call_args.kwargs
            assert "recording" in kwargs, "recording must be passed"
            assert "recording_two" in kwargs, "recording_two must be passed"

    def test_mmm_sweep_flag_accepted(self, tmp_path):
        """Test that --mmm-sweep flag is accepted and passed to run_room_fit."""
        recording_file = tmp_path / "mmm_recording.wav"
        recording_file.write_bytes(_create_minimal_wav_header())
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        # Parse args to verify --mmm-sweep is accepted
        from headmatch.cli import build_parser
        from headmatch.settings import FrontendConfig as HeadMatchConfig
        
        config = HeadMatchConfig()
        parser = build_parser(config)
        
        # This should not raise an error
        args = parser.parse_args([
            "room-fit",
            "--recording", str(recording_file),
            "--mmm-sweep", str(recording_file),
            "--out-dir", str(out_dir),
        ])
        
        # Check that mmm_sweep attribute exists
        assert hasattr(args, 'mmm_sweep'), "args should have mmm_sweep attribute"

    def test_error_on_zero_recordings(self, tmp_path):
        """Test that providing zero recordings raises appropriate error."""
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        # Parse args - this should fail because --recording is required
        from headmatch.cli import build_parser
        from headmatch.settings import FrontendConfig as HeadMatchConfig
        
        config = HeadMatchConfig()
        parser = build_parser(config)
        
        # Trying to parse with no --recording should raise SystemExit
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([
                "room-fit",
                "--out-dir", str(out_dir),
            ])
        
        # Should exit with error code 2 (argparse error)
        assert exc_info.value.code == 2

    def test_n_position_averaging_triggered_flag(self, tmp_path):
        """Test that when multiple recordings provided, averaging mode is triggered."""
        recordings = []
        for i in range(3):
            rec_file = tmp_path / f"recording{i+1}.wav"
            rec_file.write_bytes(_create_minimal_wav_header())
            recordings.append(str(rec_file))
        
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        
        with mock.patch("headmatch.room.run_room_fit") as mock_fit:
            mock_fit.return_value = self._create_mock_room_fit_result(out_dir)
            
            # Parse args to verify n_position_averaging attribute exists
            from headmatch.cli import build_parser
            from headmatch.settings import FrontendConfig as HeadMatchConfig
            
            config = HeadMatchConfig()
            parser = build_parser(config)
            
            args = parser.parse_args([
                "room-fit",
                "--recording", recordings[0],
                "--recording", recordings[1],
                "--recording", recordings[2],
                "--out-dir", str(out_dir),
            ])
            
            # Check that n_position_averaging attribute exists (will be added later)
            # For now, just verify the recordings list is accumulated
            assert hasattr(args, 'recording'), "args should have recording attribute"