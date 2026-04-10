"""File and path handling utilities.

Provides centralized path expansion and normalization helpers
used across file pickers and I/O operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


def expanded_parent(value: str, fallback: Union[str, Path]) -> str:
    """Return expanded parent directory of a path.
    
    If value is non-empty, returns the expanded parent directory.
    Otherwise returns the expanded fallback path.
    
    Args:
        value: Current path value (may be empty or whitespace)
        fallback: Default path to use when value is empty
        
    Returns:
        Expanded parent directory path as string
    """
    raw = value.strip()
    if raw:
        return str(Path(raw).expanduser().parent)
    return str(Path(fallback).expanduser())


def expanded_dir(value: str, fallback: Union[str, Path]) -> str:
    """Return expanded directory path.
    
    If value is non-empty, returns the expanded directory path.
    Otherwise returns the expanded fallback path.
    
    Args:
        value: Current directory path (may be empty or whitespace)
        fallback: Default path to use when value is empty
        
    Returns:
        Expanded directory path as string
    """
    raw = value.strip()
    if raw:
        return str(Path(raw).expanduser())
    return str(Path(fallback).expanduser())


def ensure_parent_exists(path: Union[str, Path]) -> Path:
    """Ensure parent directory of path exists, creating if needed.
    
    Args:
        path: File path whose parent should exist
        
    Returns:
        The path as a Path object
    """
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def sanitize_filename(name: str) -> str:
    """Sanitize a filename by replacing path separators.
    
    Replaces forward and backslashes with underscores to create
    a safe filename for the local filesystem.
    
    Args:
        name: Original filename that may contain path separators
        
    Returns:
        Sanitized filename safe for local filesystem use
    """
    return name.replace("/", "_").replace("\\", "_")
