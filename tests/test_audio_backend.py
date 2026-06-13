"""
Unit tests for get_audio_backend() in headmatch/audio_backend.py.
"""

import sys
from unittest.mock import patch
import pytest

from headmatch.audio_backend import get_audio_backend


def test_get_audio_backend_linux():
    """Verify PipeWireBackend is returned on Linux."""
    with patch.dict(sys.modules, {'headmatch.backend_pipewire': type('dummy', (), {'PipeWireBackend': lambda: 'PipeWireBackend'})}), patch('sys.platform', 'linux'):
        backend = get_audio_backend()
        assert backend == 'PipeWireBackend'


def test_get_audio_backend_macos():
    """Verify PortAudioBackend is returned on macOS and handles import gracefully."""
    with patch.dict(sys.modules, {'headmatch.backend_portaudio': type('dummy', (), {'PortAudioBackend': lambda: 'PortAudioBackend'})}), patch('sys.platform', 'darwin'):
        backend = get_audio_backend()
        assert backend == 'PortAudioBackend'


def test_get_audio_backend_no_backend():
    """Verify RuntimeError is raised when no backend is available."""
    with patch('sys.platform', 'win32'), patch.dict(sys.modules, {'headmatch.backend_portaudio': None}):
        with pytest.raises(RuntimeError) as excinfo:
            get_audio_backend()
        assert "No audio backend available for win32" in str(excinfo.value)


# The backend classes are mocked to avoid requiring actual imports.
# We mock the modules to return sentinel values since we only test the function's logic.