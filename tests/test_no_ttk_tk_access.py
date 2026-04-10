"""Regression test: ensure ttk.tk.* is never used.

tkinter.ttk does not have a 'tk' attribute. Canvas, DoubleVar, etc.
are in the root tkinter module, not ttk.

This test scans all Python files to prevent the bug from reappearing.
"""
import ast
import pathlib
import pytest


def test_no_ttk_tk_attribute_access():
    """Ensure no code accesses ttk.tk.* (which would raise AttributeError)."""
    headmatch_root = pathlib.Path(__file__).parent.parent
    
    violations = []
    
    for py_file in headmatch_root.rglob("*.py"):
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError:
            continue  # Skip files that can't be parsed
        
        for node in ast.walk(tree):
            # Check for attribute access pattern: something.tk.something
            if isinstance(node, ast.Attribute):
                if node.attr == "tk":
                    # Check if the parent is a Name that looks like ttk
                    if isinstance(node.value, ast.Name) and node.value.id == "ttk":
                        violations.append(f"{py_file}:{node.lineno} - 'ttk.tk' access detected")
                    # Also catch self._ttk.tk
                    elif isinstance(node.value, ast.Attribute) and node.value.attr == "_ttk":
                        violations.append(f"{py_file}:{node.lineno} - 'self._ttk.tk' access detected")
    
    assert not violations, "Found ttk.tk.* access patterns (should use tkinter directly):\n" + "\n".join(violations)


def test_no_ttk_tk_string_patterns():
    """Ensure no string patterns like 'ttk.tk.' exist in source files."""
    headmatch_root = pathlib.Path(__file__).parent.parent
    
    violations = []
    
    for py_file in headmatch_root.rglob("*.py"):
        source = py_file.read_text()
        for i, line in enumerate(source.splitlines(), 1):
            if "ttk.tk." in line and "ttk.tk." not in line.split("#")[0]:  # Ignore comments
                violations.append(f"{py_file}:{i} - {line.strip()}")
    
    assert not violations, "Found 'ttk.tk.' string patterns:\n" + "\n".join(violations)
