"""Tests for headmatch.gui.filepicker module."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from headmatch.gui import filepicker


class TestGetOpenFilename:
    """Tests for get_open_filename function."""

    def test_delegates_to_askopenfilename(self):
        """Test that get_open_filename delegates to askopenfilename."""
        with patch('headmatch.gui.filepicker.filedialog.askopenfilename') as mock_dialog:
            mock_dialog.return_value = '/path/to/file.csv'
            
            result = filepicker.get_open_filename(
                parent=None,
                title='Select CSV',
                filetypes=[('CSV files', '*.csv')],
            )
            
            assert result == '/path/to/file.csv'
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Select CSV',
                filetypes=[('CSV files', '*.csv')],
                initialdir=None,
            )

    def test_returns_none_on_cancel(self):
        """Test that None is returned when user cancels dialog."""
        with patch('headmatch.gui.filepicker.filedialog.askopenfilename') as mock_dialog:
            mock_dialog.return_value = ''
            
            result = filepicker.get_open_filename(
                parent=None,
                title='Select CSV',
                filetypes=[('CSV files', '*.csv')],
            )
            
            assert result is None

    def test_passes_initialdir_when_provided(self):
        """Test that initialdir is passed when provided."""
        with patch('headmatch.gui.filepicker.filedialog.askopenfilename') as mock_dialog:
            mock_dialog.return_value = '/path/to/file.csv'
            
            filepicker.get_open_filename(
                parent=None,
                title='Select CSV',
                filetypes=[('CSV files', '*.csv')],
                initialdir='/home/user',
            )
            
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Select CSV',
                filetypes=[('CSV files', '*.csv')],
                initialdir='/home/user',
            )


class TestGetSaveFilename:
    """Tests for get_save_filename function."""

    def test_delegates_to_asksaveasfilename(self):
        """Test that get_save_filename delegates to asksaveasfilename."""
        with patch('headmatch.gui.filepicker.filedialog.asksaveasfilename') as mock_dialog:
            mock_dialog.return_value = '/path/to/save.txt'
            
            result = filepicker.get_save_filename(
                parent=None,
                title='Save File',
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt')],
            )
            
            assert result == '/path/to/save.txt'
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Save File',
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt')],
                initialdir=None,
            )

    def test_returns_none_on_cancel(self):
        """Test that None is returned when user cancels dialog."""
        with patch('headmatch.gui.filepicker.filedialog.asksaveasfilename') as mock_dialog:
            mock_dialog.return_value = ''
            
            result = filepicker.get_save_filename(
                parent=None,
                title='Save File',
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt')],
            )
            
            assert result is None

    def test_passes_initialdir_when_provided(self):
        """Test that initialdir is passed when provided."""
        with patch('headmatch.gui.filepicker.filedialog.asksaveasfilename') as mock_dialog:
            mock_dialog.return_value = '/path/to/save.txt'
            
            filepicker.get_save_filename(
                parent=None,
                title='Save File',
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt')],
                initialdir='/home/user',
            )
            
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Save File',
                defaultextension='.txt',
                filetypes=[('Text files', '*.txt')],
                initialdir='/home/user',
            )


class TestGetDirectory:
    """Tests for get_directory function."""

    def test_delegates_to_askdirectory(self):
        """Test that get_directory delegates to askdirectory."""
        with patch('headmatch.gui.filepicker.filedialog.askdirectory') as mock_dialog:
            mock_dialog.return_value = '/path/to/dir'
            
            result = filepicker.get_directory(
                parent=None,
                title='Select Directory',
            )
            
            assert result == '/path/to/dir'
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Select Directory',
                initialdir=None,
            )

    def test_returns_none_on_cancel(self):
        """Test that None is returned when user cancels dialog."""
        with patch('headmatch.gui.filepicker.filedialog.askdirectory') as mock_dialog:
            mock_dialog.return_value = ''
            
            result = filepicker.get_directory(
                parent=None,
                title='Select Directory',
            )
            
            assert result is None

    def test_passes_initialdir_when_provided(self):
        """Test that initialdir is passed when provided."""
        with patch('headmatch.gui.filepicker.filedialog.askdirectory') as mock_dialog:
            mock_dialog.return_value = '/path/to/dir'
            
            filepicker.get_directory(
                parent=None,
                title='Select Directory',
                initialdir='/home/user',
            )
            
            mock_dialog.assert_called_once_with(
                parent=None,
                title='Select Directory',
                initialdir='/home/user',
            )