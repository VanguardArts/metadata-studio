"""Unified data model shared by every engine and the GUI/CLI.

Every input file is reduced to a :class:`FileReport` containing a flat list of
:class:`Finding` records. Engines set a per-finding ``action`` (what the
sanitizer will do) and ``severity`` (how much we care), so the GUI can colour
the table and the CLI can render uniformly regardless of the underlying format.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Finding:
    """A single piece of metadata discovered in (or about) a file."""

    key: str            # e.g. "EXIF:DateTimeOriginal", "ID3:COMM", "PDF:/Author"
    value: str          # human-readable preview (truncated)
    action: str         # strip | set | keep | flag | review
    kind: str = ""      # provenance | personal | audio | document | tag
    severity: str = "info"  # info | warning | critical


@dataclass
class FileReport:
    """Result of inspecting (or sanitizing) one file."""

    path: str
    format: str                         # "png", "mp3", "pdf", "docx", ...
    category: str = "unknown"           # image | audio | document | other
    findings: List[Finding] = field(default_factory=list)
    declared_watermark: bool = False    # C2PA manifest asserts c2pa.watermarked.*
    skipped: bool = False
    error: Optional[str] = None

    # filled by the sanitizer after a run
    sanitized: bool = False
    bytes_in: int = 0
    bytes_out: int = 0
    psnr_db: Optional[float] = None

    def counts(self):
        strip = sum(1 for f in self.findings if f.action == "strip")
        setn = sum(1 for f in self.findings if f.action == "set")
        keep = sum(1 for f in self.findings if f.action == "keep")
        flag = sum(1 for f in self.findings if f.action == "flag")
        return strip, setn, keep, flag

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompareResult:
    """Before/after diff for a single file, for the comparison view."""

    path: str
    before: FileReport
    after: FileReport

    def removed(self) -> List[Finding]:
        before_keys = {(f.key, f.value) for f in self.before.findings}
        after_keys = {(f.key, f.value) for f in self.after.findings}
        removed = [f for f in self.before.findings if (f.key, f.value) not in after_keys]
        return removed

    def remaining(self) -> List[Finding]:
        return self.after.findings

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
            "removed": [asdict(f) for f in self.removed()],
            "remaining": [asdict(f) for f in self.remaining()],
        }
