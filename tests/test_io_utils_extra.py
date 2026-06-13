import json
import tempfile
from pathlib import Path

import pytest

from headmatch.io_utils import save_json


def test_save_json_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nested" / "data.json"
        data = {"key": "value"}
        
        save_json(path, data)
        
        assert path.exists()
        assert path.parent.exists()
        

def test_save_json_valid_json_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "data.json"
        data = {"key": "value"}
        
        save_json(path, data)
        
        # Load and parse it back
        loaded_data = json.loads(path.read_text())
        assert loaded_data == data
        

def test_save_json_handles_nested_dictionaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "data.json"
        data = {
            "outer": {
                "inner": {
                    "deep": "value"
                },
                "list": [1, 2, 3]
            }
        }
        
        save_json(path, data)
        
        loaded_data = json.loads(path.read_text())
        assert loaded_data == data
        

def test_save_json_handles_empty_dictionary():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "data.json"
        data = {}
        
        save_json(path, data)
        
        loaded_data = json.loads(path.read_text())
        assert loaded_data == data
        assert path.read_text().strip() == "{}"