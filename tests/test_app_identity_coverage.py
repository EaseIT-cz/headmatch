"""Coverage tests for app_identity.py missing lines.

Targets: 22 (version_display when a build is set).
"""
from __future__ import annotations

from headmatch.app_identity import AppIdentity, get_app_identity


def test_version_display_with_build():
    identity = AppIdentity(
        name="headmatch",
        display_name="HeadMatch",
        version="1.2.3",
        package_version="1.2.3",
        build="abc123",
    )
    assert identity.version_display == "1.2.3+abc123"


def test_version_display_without_build():
    identity = get_app_identity()
    assert identity.build is None
    assert identity.version_display == identity.version
