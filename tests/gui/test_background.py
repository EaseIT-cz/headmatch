"""Tests for headmatch.gui.background module."""
from __future__ import annotations

import threading
import pytest
from unittest.mock import patch, MagicMock, call

from headmatch.gui import background


class TestRunInThread:
    """Tests for run_in_thread function."""

    def test_creates_and_starts_thread(self):
        """Test that run_in_thread creates and starts a thread."""
        mock_thread = MagicMock()
        
        with patch('headmatch.gui.background.threading.Thread', return_value=mock_thread):
            result = background.run_in_thread(lambda: None)
            
            assert result is mock_thread
            mock_thread.start.assert_called_once()

    def test_thread_is_daemon_by_default(self):
        """Test that thread is daemon by default."""
        with patch('headmatch.gui.background.threading.Thread') as mock_thread_class:
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread
            
            background.run_in_thread(lambda: None)
            
            mock_thread_class.assert_called_once()
            assert mock_thread_class.call_args[1]['daemon'] is True

    def test_thread_daemon_can_be_false(self):
        """Test that daemon can be set to False."""
        with patch('headmatch.gui.background.threading.Thread') as mock_thread_class:
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread
            
            background.run_in_thread(lambda: None, daemon=False)
            
            assert mock_thread_class.call_args[1]['daemon'] is False

    def test_passes_args_to_target_function(self):
        """Test that args are passed to the target function."""
        calls = []
        
        def worker(a, b, c):
            calls.append((a, b, c))
        
        with patch('headmatch.gui.background.threading.Thread') as mock_thread_class:
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread
            
            # Capture the target function
            background.run_in_thread(worker, 1, 2, c=3)
            
            # The target should be a wrapper that calls worker with args
            target = mock_thread_class.call_args[1]['target']
            target()  # Execute the wrapper
            
            assert calls == [(1, 2, 3)]


class TestWorkerFunction:
    """Tests for the worker function behavior."""

    def test_calls_function_with_args(self):
        """Test that worker calls the function with provided args."""
        calls = []
        
        def func(a, b, c=None):
            calls.append((a, b, c))
            return 'result'
        
        background._worker(func, (1, 2), {'c': 3})
        
        assert calls == [(1, 2, 3)]

    def test_returns_result_on_success(self):
        """Test that worker returns result on success."""
        def func():
            return 'success'
        
        result = background._worker(func, (), {})
        
        assert result == 'success'

    def test_calls_on_error_when_exception_raises(self):
        """Test that on_error is called when function raises."""
        error_calls = []
        
        def func():
            raise ValueError('test error')
        
        def on_error(exc):
            error_calls.append(exc)
        
        background._worker(func, (), {}, on_error=on_error)
        
        assert len(error_calls) == 1
        assert isinstance(error_calls[0], ValueError)
        assert str(error_calls[0]) == 'test error'

    def test_adds_exception_info_to_result_when_error(self):
        """Test that exception info is added to result when error occurs."""
        def func():
            raise ValueError('test error')
        
        result = background._worker(func, (), {})
        
        assert result is None  # on_error was None, so no return value


class TestRunInThreadIntegration:
    """Integration tests for run_in_thread with actual threading."""

    def test_function_executed_in_separate_thread(self):
        """Test that function runs in a separate thread."""
        main_thread = threading.current_thread()
        worker_thread = []
        
        def capture_thread():
            worker_thread.append(threading.current_thread())
        
        thread = background.run_in_thread(capture_thread)
        thread.join(timeout=2)
        
        assert len(worker_thread) == 1
        assert worker_thread[0] is not main_thread
        assert worker_thread[0] is thread

    def test_result_returned_from_function(self):
        """Test that function result is returned."""
        results = []
        
        def worker():
            return 42
        
        def capture_result(result):
            results.append(result)
        
        thread = background.run_in_thread(worker, on_success=capture_result)
        thread.join(timeout=2)
        
        assert results == [42]

    def test_error_handled_via_callback(self):
        """Test that errors are handled via on_error callback."""
        errors = []
        
        def failing():
            raise RuntimeError('fail')
        
        def capture_error(exc):
            errors.append(exc)
        
        thread = background.run_in_thread(failing, on_error=capture_error)
        thread.join(timeout=2)
        
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)