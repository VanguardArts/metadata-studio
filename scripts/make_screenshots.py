#!/usr/bin/env python3
"""Generate real offscreen screenshots of the Metascrub GUI.

Runs the actual PySide6 MainWindow with the Qt offscreen platform, feeds it a
genuine sample set spanning images, audio and documents (each carrying
identifying metadata), then captures two frames: the Inspect view (unified
findings across formats) and the Compare view (before/after sanitization).

Usage:
    QT_QPA_PLATFORM=offscreen python3 scripts/make_screenshots.py
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image
from PySide6.QtWidgets import QApplication

from metascrub.gui.app import MainWindow

SCREENSHOTS = ROOT / "docs"


# --- sample builders (mirror the test_engine fixtures) ----------------------

def make_png(path: Path, with_exif: bool = True) -> Path:
    im = Image.new("RGB", (10, 10), (255, 0, 0))
    if with_exif:
        exif = Image.Exif()
        exif[0x0110] = "TestCam"          # Model
        im.save(path, exif=exif)
    else:
        im.save(path)
    return path


def make_mp3(path: Path) -> Path:
    from mutagen.id3 import COMM, ID3, TIT2
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Test Song"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["made with Suno"]))
    tags.save(path)
    with open(path, "ab") as fh:
        fh.write(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    return path


def make_pdf(path: Path) -> Path:
    info = (b"<< /Type /Info /Author (Jane Doe) /Creator (FooBar 1.0) "
            b"/CreationDate (D:20260101000000Z) >>")
    body = (b"%PDF-1.4\n"
            b"1 0 obj\n" + info + b"\nendobj\n"
            b"2 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n"
            b"3 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
    xref = b"xref\n0 4\n0000000000 65535 f \ntrailer\n<< /Info 1 0 R /Root 2 0 R /Size 4 >>\n"
    path.write_bytes(body + xref)
    return path


def make_docx(path: Path) -> Path:
    core = (b'<?xml version="1.0"?><cp:coreProperties '
            b'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            b'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            b'xmlns:dcterms="http://purl.org/dc/terms/">'
            b'<dc:creator>Jane Doe</dc:creator>'
            b'<dc:title>Secret Report</dc:title>'
            b'<cp:lastModifiedBy>JD</cp:lastModifiedBy>'
            b'</cp:coreProperties>')
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("docProps/core.xml", core)
        zf.writestr("word/document.xml", b"<w:document/>")
    return path


def _grab(window: MainWindow, path: Path) -> None:
    window.show()
    QApplication.processEvents()
    QApplication.processEvents()
    window.grab().save(str(path))


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        make_png(root / "photo.png", with_exif=True)
        make_mp3(root / "song.mp3")
        make_pdf(root / "report.pdf")
        make_docx(root / "notes.docx")

        win = MainWindow()

        # --- Inspect view: unified findings across image/audio/document ---
        inspect_tab = win.inspect_tab
        inspect_tab.path_edit.setText(str(root))
        inspect_tab._scan()
        win.tabs.setCurrentIndex(0)
        _grab(win, SCREENSHOTS / "screenshot-inspect.png")

        # --- Compare view: before/after for a single image -----------------
        compare_tab = win.compare_tab
        compare_tab.path_edit.setText(str(root / "photo.png"))
        compare_tab._run()
        win.tabs.setCurrentIndex(2)
        _grab(win, SCREENSHOTS / "screenshot-compare.png")

    print(f"Wrote {SCREENSHOTS / 'screenshot-inspect.png'}")
    print(f"Wrote {SCREENSHOTS / 'screenshot-compare.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
