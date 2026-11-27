"""Tests for the Metascrub unified engine."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from metascrub.core import service
from metascrub.core.dispatch import category_for, is_supported
from metascrub.engines import audio, document, image


def _make_png(path: Path, with_exif=False):
    im = Image.new("RGB", (10, 10), (255, 0, 0))
    if with_exif:
        from PIL import Image as I
        exif = I.Exif()
        exif[0x0110] = "TestCam"  # Model
        im.save(path, exif=exif)
    else:
        im.save(path)


def _make_mp3(path: Path):
    # minimal ID3v2.4 tag with a comment + origin URL
    from mutagen.id3 import COMM, ID3, TIT2
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Test Song"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["made with Suno"]))
    tags.save(path)
    # append a minimal (empty) MPEG frame so the file has audio bytes
    with open(path, "ab") as fh:
        fh.write(b"\xff\xfb\x90\x00" + b"\x00" * 100)


def _make_pdf(path: Path):
    # a hand-built minimal PDF with an /Info dict carrying an Author
    info = (b"<< /Type /Info /Author (Jane Doe) /Creator (FooBar 1.0) "
            b"/CreationDate (D:20260101000000Z) >>")
    body = (b"%PDF-1.4\n"
            b"1 0 obj\n" + info + b"\nendobj\n"
            b"2 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n"
            b"3 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
    xref = b"xref\n0 4\n0000000000 65535 f \ntrailer\n<< /Info 1 0 R /Root 2 0 R /Size 4 >>\n"
    path.write_bytes(body + xref)


def _make_docx(path: Path):
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


def test_category_dispatch():
    assert category_for("a.png") == "image"
    assert category_for("a.mp3") == "audio"
    assert category_for("a.pdf") == "document"
    assert category_for("a.xyz") == "other"
    assert is_supported("a.docx")
    assert not is_supported("a.txt")


def test_image_inspect_and_strip(tmp_path):
    p = tmp_path / "img.png"
    _make_png(p, with_exif=True)
    rep = image.inspect(p)
    assert rep.category == "image"
    keys = " ".join(f.key for f in rep.findings)
    assert "eXIf" in keys or "EXIF" in keys or "Model" in keys

    clean = image.sanitize(p, level=0)
    assert clean.sanitized
    assert clean.bytes_out > 0
    assert clean._ext == "png"


def test_audio_inspect_and_clean(tmp_path):
    p = tmp_path / "song.mp3"
    _make_mp3(p)
    rep = audio.inspect(p)
    assert any(f.key.startswith("ID3:COMM") and f.action == "strip"
               for f in rep.findings)

    clean = audio.sanitize(p, dry_run=False)
    assert clean.sanitized
    after = audio.inspect(p)
    assert not any(f.key.startswith("ID3:COMM") for f in after.findings)


def test_document_pdf_inspect(tmp_path):
    p = tmp_path / "doc.pdf"
    _make_pdf(p)
    rep = document.inspect(p)
    assert rep.category == "document"
    keys = " ".join(f.key for f in rep.findings)
    assert "Author" in keys or "Creator" in keys


def test_document_docx_inspect(tmp_path):
    p = tmp_path / "doc.docx"
    _make_docx(p)
    rep = document.inspect(p)
    assert rep.category == "document"
    assert any("Jane" in f.value or "Jane" in f.key for f in rep.findings
               if f.action == "strip")


def test_service_inspect(tmp_path):
    p = tmp_path / "img.png"
    _make_png(p)
    rep = service.inspect(p)
    assert rep.category == "image"


def test_document_html_inspect(tmp_path):
    p = tmp_path / "page.html"
    p.write_text('<html><head><meta name="author" content="Jane Doe">'
                 '<meta name="generator" content="Hugo"></head><body/></html>')
    rep = document.inspect(p)
    assert rep.category == "document"
    assert any("Jane Doe" in f.value for f in rep.findings)


def test_document_rtf_inspect(tmp_path):
    p = tmp_path / "doc.rtf"
    p.write_text(r'{\rtf1\ansi {\info {\author Jane Doe}{\company ACME}'
                 r'{\title Report}}\par Hello}')
    rep = document.inspect(p)
    assert rep.category == "document"
    assert any("Jane Doe" in f.value for f in rep.findings)


def test_document_svg_inspect(tmp_path):
    p = tmp_path / "art.svg"
    p.write_text('<svg xmlns:dc="http://purl.org/dc/elements/1.1/">'
                 '<metadata><dc:creator>Jane Doe</dc:creator>'
                 '<dc:title>My Art</dc:title></metadata></svg>')
    rep = document.inspect(p)
    assert rep.category == "document"
    assert any("Jane Doe" in f.value for f in rep.findings)


def test_document_epub_inspect(tmp_path):
    p = tmp_path / "book.epub"
    opf = ('<?xml version="1.0"?><package>'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<dc:creator>Jane Doe</dc:creator><dc:title>My Book</dc:title>'
           '</metadata></package>')
    container = ('<?xml version="1.0"?><container>'
                 '<rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/></container>')
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("mimetype", b"application/epub+zip")
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
    rep = document.inspect(p)
    assert rep.category == "document"
    assert any("Jane Doe" in f.value for f in rep.findings)
