"""File-type detection and category/extension registry.

A single source of truth mapping every supported file kind to its engine
category, so the GUI "Add files" picker, the CLI, and the watcher all agree on
what is processable and which engine handles it.
"""
from __future__ import annotations

from pathlib import Path

# Images handled by the provenance/image engine (mirrors image-scrub).
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}

# Audio handled by the audio engine (mirrors audio-scrub; FLAC/OGG/M4A are
# intentionally listed as unsupported until adapters land — see README).
AUDIO_EXTS = {".mp3", ".wav"}

# Documents handled by the document-metadata engine (new in this project).
DOCUMENT_EXTS = {
    ".pdf",
    ".docx", ".xlsx", ".pptx",   # Office Open XML (zip + docProps/core.xml)
    ".odt", ".ods", ".odp",       # OpenDocument (zip + meta.xml)
    ".epub",                        # EPUB (zip + OPF dc: metadata)
    ".html", ".htm", ".xhtml",     # HTML (meta tags)
    ".rtf",                         # Rich Text (\info group)
    ".svg",                         # SVG (dc/RDF metadata)
}

ALL_EXTS = IMAGE_EXTS | AUDIO_EXTS | DOCUMENT_EXTS


def category_for(path: str | Path) -> str:
    """Return 'image', 'audio', 'document', or 'other' for a path."""
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in AUDIO_EXTS:
        return "audio"
    if suffix in DOCUMENT_EXTS:
        return "document"
    return "other"


def is_supported(path: str | Path) -> bool:
    return category_for(path) != "other"


def iter_supported(paths):
    """Filter an iterable of paths to only the supported ones."""
    for p in paths:
        if is_supported(p):
            yield p
