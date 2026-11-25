"""Engine adapters: image (EXIF/C2PA/XMP/IPTC), audio (ID3/RIFF), document.

Each engine exposes a uniform interface:

    inspect(path) -> FileReport      # read-only
    sanitize(path, options) -> FileReport  # strip + (optionally) transform
"""
from __future__ import annotations

from ..core.model import FileReport, Finding


def _finding(key: str, value: str, action: str, kind: str = "",
             severity: str = "info") -> Finding:
    return Finding(key=key, value=value, action=action, kind=kind, severity=severity)


__all__ = ["Finding", "FileReport", "_finding"]
