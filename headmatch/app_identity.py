from __future__ import annotations

from dataclasses import dataclass


APP_NAME = 'headmatch'
APP_DISPLAY_NAME = 'HeadMatch'
_VERSION = '0.7.0'


@dataclass(frozen=True)
class AppIdentity:
    name: str
    display_name: str
    version: str
    package_version: str
    build: str | None

    @property
    def version_display(self) -> str:
        if self.build:
            return f'{self.version}+{self.build}'
        return self.version

    def as_metadata(self) -> dict:
        return {
            'name': self.name,
            'display_name': self.display_name,
            'version': self.version,
            'package_version': self.package_version,
            'build': self.build,
            'version_display': self.version_display,
        }


__version__ = _VERSION


def get_app_identity() -> AppIdentity:
    return AppIdentity(
        name=APP_NAME,
        display_name=APP_DISPLAY_NAME,
        version=__version__,
        package_version=__version__,
        build=None,
    )
