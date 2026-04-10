"""Navigation items and view routing data.

This module contains navigation constants and routing logic
for the HeadMatch GUI shell.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationItem:
    """Represents a navigation button in the GUI sidebar."""
    key: str
    label: str


# Navigation items for basic mode (simplified workflow)
BASIC_NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("basic-mode", "Basic Workflow"),
    NavigationItem("basic-clone-target", "Clone Target"),
    NavigationItem("history", "Results"),
)

# Navigation items for advanced mode (full feature set)
NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("measure-online", "Measure"),
    NavigationItem("setup-check", "Setup Check"),
    NavigationItem("prepare-offline", "Prepare Offline"),
    NavigationItem("target-editor", "Target Editor"),
    NavigationItem("import-apo", "Import APO"),
    NavigationItem("fetch-curve", "Fetch Curve"),
    NavigationItem("history", "Results"),
)


def nav_items_for_mode(mode: str) -> tuple[NavigationItem, ...]:
    """Return navigation items appropriate for the given mode."""
    return BASIC_NAV_ITEMS if mode == "basic" else NAV_ITEMS
