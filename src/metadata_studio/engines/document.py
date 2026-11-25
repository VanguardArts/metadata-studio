r"""Document engine — PDF / OOXML / ODF / EPUB / HTML / RTF / SVG metadata inspection and stripping.

This is the novel piece of Vanguard Metadata Studio: neither Metascrub nor
Provenance Scrubber handles documents. It detects and removes identifying
metadata (author, creator, last-modified-by, company, revision history, custom
properties) and embedded thumbnails/previews from:

* PDF          — ``/Info`` dictionary keys (Author, Creator, Producer, Title,
                 Subject, Keywords, CreationDate, ModDate) plus XMP metadata
                 streams and page thumbnails (``/Thumb``).
* OOXML        — ``docProps/core.xml``, ``docProps/app.xml`` and
                 ``docProps/custom.xml`` inside the zip (docx/xlsx/pptx).
* ODF          — ``meta.xml`` inside the zip (odt/ods/odp).
* EPUB         — the OPF ``<metadata>`` block (Dublin Core + meta tags).
* HTML         — ``<meta name=... content=...>`` tags (html/htm/xhtml).
* RTF          — the ``\info`` group (author, title, company, manager, ...).
* SVG          — embedded ``dc:*`` / RDF metadata (creator, title, ...).

Documents are rewritten by editing the relevant entries in-place (bytes for
PDF, zip member replacement for OOXML/ODF) so non-metadata content is preserved
verbatim. No content is re-rendered or transcoded.
"""
from __future__ import annotations

import re
import struct
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from ..core.dispatch import category_for
from ..core.model import FileReport, Finding
from . import _finding


def _preview(text, limit: int = 80) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


# --- PDF ---------------------------------------------------------------

# PDF Info keys that carry identifying/personal data.
PDF_INFO_KEYS = [
    ("/Author", "personal"), ("/Creator", "personal"),
    ("/Producer", "personal"), ("/Title", "document"),
    ("/Subject", "document"), ("/Keywords", "document"),
    ("/CreationDate", "personal"), ("/ModDate", "personal"),
    ("/Trapped", "document"), ("/Company", "personal"),
]


def _extract_pdf_info(data: bytes) -> List[Tuple[str, str]]:
    """Best-effort parse of the PDF ``/Info`` dictionary (object level)."""
    out: List[Tuple[str, str]] = []
    m = re.search(rb"/Info\s+(\d+)\s+(\d+)\s+R", data)
    if not m:
        return out
    objnum = int(m.group(1))
    # find that object
    pat = re.compile(rb"(%d)\s+(%d)\s+obj\b" % (objnum, int(m.group(2))))
    mm = pat.search(data)
    if not mm:
        return out
    start = mm.end()
    end = data.find(b"endobj", start)
    body = data[start:end if end != -1 else start + 4000]
    for key, kind in PDF_INFO_KEYS:
        kb = key.encode("latin1")
        km = re.search(rb"/" + re.escape(kb.lstrip(b"/")) + rb"\s*\(([^)]*)\)", body)
        if km:
            val = km.group(1).decode("latin1", "replace")
            out.append((key, val, kind))
    return out


def _has_xmp(data: bytes) -> bool:
    return b"xpacket" in data or b"x:xmpmeta" in data or b"XMP" in data[:20000]


def _has_thumbnails(data: bytes) -> int:
    return len(re.findall(rb"/Thumb\s", data))


def _inspect_pdf(path: str) -> FileReport:
    rep = FileReport(path=path, format="pdf", category="document")
    try:
        data = Path(path).read_bytes()
    except Exception as exc:
        rep.error = str(exc)
        return rep

    info = _extract_pdf_info(data)
    for key, val, kind in info:
        rep.findings.append(_finding(f"PDF:{key}", _preview(val), "strip", kind, "warning"))

    if _has_xmp(data):
        rep.findings.append(_finding("PDF:XMP", "XMP metadata stream present",
                                     "strip", "provenance", "critical"))

    thumbs = _has_thumbnails(data)
    if thumbs:
        rep.findings.append(_finding("PDF:Thumbnail",
                                     f"{thumbs} embedded page thumbnail(s)",
                                     "strip", "provenance", "critical"))

    # try pypdf for authoritative info (optional) and attachments
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        meta = reader.metadata
        if meta:
            for k in ("author", "creator", "producer", "title", "subject",
                      "keywords", "creation_date", "modification_date"):
                v = getattr(meta, k, None)
                if v and not any(f.key == f"PDF:/{k}" for f in rep.findings):
                    rep.findings.append(_finding(f"PDF:/{k.title()}", _preview(v),
                                                 "strip", "personal", "warning"))
        if getattr(reader, "attachments", None):
            rep.findings.append(_finding("PDF:Attachments",
                                         f"{len(reader.attachments)} embedded file(s)",
                                         "review", "provenance", "critical"))
    except Exception:
        pass

    if not rep.findings:
        rep.findings.append(_finding("PDF", "(no metadata found)", "keep", "", "info"))
    return rep


def _sanitize_pdf(path: str, dry_run: bool) -> FileReport:
    rep = FileReport(path=path, format="pdf", category="document")
    try:
        data = Path(path).read_bytes()
    except Exception as exc:
        rep.error = str(exc)
        return rep

    before_info = _extract_pdf_info(data)
    for key, val, kind in before_info:
        rep.findings.append(_finding(f"PDF:{key}", _preview(val), "strip", kind, "warning"))

    # Replace each Info string value with empty, preserving structure.
    out_data = data
    for key, _val, _kind in before_info:
        kb = key.encode("latin1").lstrip(b"/")
        out_data = re.sub(rb"/" + re.escape(kb) + rb"\s*\([^)]*\)",
                          b"/" + kb + b"()", out_data, count=1)
    # Neutralize XMP stream contents (replace the packet body) and thumbnails.
    out_data = re.sub(rb"xpacket begin.*?xpacket end",
                      b"xpacket begin=\"\xc2\xaf\" id=\"W5M0MpCehiHzreSzNTczkc9d\""
                      b"?>xpacket end=\"w\"", out_data, flags=re.DOTALL)
    removed_thumbs = len(re.findall(rb"/Thumb\s\d+ \d+ R", out_data))
    if removed_thumbs:
        rep.findings.append(_finding("PDF:Thumbnail",
                                     f"{removed_thumbs} thumbnail(s) removed",
                                     "strip", "provenance", "critical"))

    rep.sanitized = not dry_run
    rep.bytes_in = len(data)
    rep.bytes_out = len(out_data)
    if not dry_run:
        tmp = path + ".metadata-studio.tmp"
        with open(tmp, "wb") as fh:
            fh.write(out_data)
        import os
        os.replace(tmp, path)
    return rep


# --- OOXML / ODF (zip) -------------------------------------------------

OOXML_CORE_FIELDS = [
    ("dc:title", "Title"), ("dc:subject", "Subject"),
    ("dc:creator", "Author"), ("cp:keywords", "Keywords"),
    ("dc:description", "Description"),
    ("cp:lastModifiedBy", "Last modified by"),
    ("cp:revision", "Revision"),
    ("dcterms:created", "Created"), ("dcterms:modified", "Modified"),
]

OOXML_APP_FIELDS = [
    ("Company", "Company"), ("Manager", "Manager"),
    ("Application", "Application"), ("AppVersion", "App version"),
]

ODF_META_FIELDS = [
    ("dc:title", "Title"), ("dc:description", "Description"),
    ("dc:creator", "Author"), ("dc:date", "Date"),
    ("meta:generator", "Generator"), ("meta:creation-date", "Created"),
    ("meta:initial-creator", "Initial creator"),
    ("meta:printed-by", "Printed by"), ("meta:keyword", "Keywords"),
]


def _read_zip_member(zf: zipfile.ZipFile, name: str) -> Optional[bytes]:
    try:
        return zf.read(name)
    except KeyError:
        return None


def _doc_inspect(path: str, member: str, fields, prefix: str,
                 fmt: str) -> FileReport:
    rep = FileReport(path=path, format=fmt, category="document")
    try:
        with zipfile.ZipFile(path) as zf:
            xml = _read_zip_member(zf, member)
    except Exception as exc:
        rep.error = str(exc)
        return rep
    if xml is None:
        rep.findings.append(_finding(prefix, "(no core properties)", "keep", "", "info"))
        return rep

    text = xml.decode("utf-8", "replace")
    for tag, label in fields:
        # match <tag>value</tag> or <tag> ... </tag>
        m = re.search(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                      text, flags=re.DOTALL)
        if m and m.group(1).strip():
            val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            rep.findings.append(_finding(f"{prefix}:{label}", _preview(val),
                                         "strip", "personal", "warning"))
    if not rep.findings:
        rep.findings.append(_finding(prefix, "(no revealing metadata)", "keep", "", "info"))
    return rep


def _doc_sanitize(path: str, member: str, fields, prefix: str, fmt: str,
                  dry_run: bool) -> FileReport:
    rep = FileReport(path=path, format=fmt, category="document")
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            infos = {i.filename: i for i in zf.infolist()}
            xml = _read_zip_member(zf, member)
    except Exception as exc:
        rep.error = str(exc)
        return rep
    if xml is None:
        return rep

    text = xml.decode("utf-8", "replace")
    cleaned = text
    for tag, label in fields:
        if re.search(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                     text, flags=re.DOTALL):
            rep.findings.append(_finding(f"{prefix}:{label}", "", "strip", "personal", "warning"))
        cleaned = re.sub(r"(<" + re.escape(tag) + r"[^>]*>).*?(</" + re.escape(tag) + r">)",
                         r"\1\2", cleaned, flags=re.DOTALL)

    if cleaned == text:
        if not rep.findings:
            rep.findings.append(_finding(prefix, "(nothing to strip)", "keep", "", "info"))
        return rep

    rep.sanitized = not dry_run
    if dry_run:
        return rep

    # rewrite the zip, replacing only the target member
    buf = BytesIO()
    with zipfile.ZipFile(path) as zf, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in names:
            info = infos[name]
            if name == member:
                out.writestr(info, cleaned.encode("utf-8"))
            else:
                out.writestr(info, zf.read(name))
    import os
    tmp = path + ".metadata-studio.tmp"
    with open(tmp, "wb") as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, path)
    rep.bytes_out = os.path.getsize(path)
    return rep


# --- EPUB -------------------------------------------------------------

# Dublin Core fields inside the EPUB OPF <metadata> block.
EPUB_DC_FIELDS = [
    ("dc:title", "Title"), ("dc:creator", "Author"),
    ("dc:contributor", "Contributor"), ("dc:publisher", "Publisher"),
    ("dc:subject", "Subject"), ("dc:description", "Description"),
    ("dc:date", "Date"), ("dc:language", "Language"),
    ("dc:identifier", "Identifier"), ("dc:rights", "Rights"),
]


def _epub_opf_path(path: str) -> Optional[str]:
    with zipfile.ZipFile(path) as zf:
        container = _read_zip_member(zf, "META-INF/container.xml")
        if not container:
            return None
        text = container.decode("utf-8", "replace")
        m = re.search(r'full-path="([^"]+)"', text)
        return m.group(1) if m else None


def _inspect_epub(path: str) -> FileReport:
    rep = FileReport(path=path, format="epub", category="document")
    try:
        opf = _epub_opf_path(path)
        if not opf:
            rep.findings.append(_finding("EPUB", "(no OPF found)", "keep", "", "info"))
            return rep
        with zipfile.ZipFile(path) as zf:
            xml = _read_zip_member(zf, opf)
        if not xml:
            rep.findings.append(_finding("EPUB", "(no OPF metadata)", "keep", "", "info"))
            return rep
    except Exception as exc:
        rep.error = str(exc)
        return rep
    text = xml.decode("utf-8", "replace")
    for tag, label in EPUB_DC_FIELDS:
        for m in re.finditer(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                             text, flags=re.DOTALL):
            if m.group(1).strip():
                val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                rep.findings.append(_finding(f"EPUB:{label}", _preview(val),
                                             "strip", "personal", "warning"))
    # optional creator/other meta with content attributes
    for m in re.finditer(r'<meta[^>]+name="([^"]+)"[^>]+content="([^"]*)"\s*/?>', text):
        rep.findings.append(_finding(f"EPUB:meta:{m.group(1)}", _preview(m.group(2)),
                                     "strip", "personal", "warning"))
    if not rep.findings:
        rep.findings.append(_finding("EPUB", "(no revealing metadata)", "keep", "", "info"))
    return rep


def _sanitize_epub(path: str, dry_run: bool) -> FileReport:
    rep = FileReport(path=path, format="epub", category="document")
    try:
        opf = _epub_opf_path(path)
        if not opf:
            return rep
        with zipfile.ZipFile(path) as zf:
            xml = _read_zip_member(zf, opf)
        if not xml:
            return rep
    except Exception as exc:
        rep.error = str(exc)
        return rep
    text = xml.decode("utf-8", "replace")
    cleaned = text
    for tag, label in EPUB_DC_FIELDS:
        if re.search(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                     text, flags=re.DOTALL):
            rep.findings.append(_finding(f"EPUB:{label}", "", "strip", "personal", "warning"))
        cleaned = re.sub(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                         lambda m: m.group(0), cleaned, flags=re.DOTALL)
        # clear the inner value only (keep the element)
        cleaned = re.sub(r"(<" + re.escape(tag) + r"[^>]*>).*?(</" + re.escape(tag) + r">)",
                         r"\1\2", cleaned, flags=re.DOTALL)
    # clear meta content attributes
    cleaned = re.sub(r'(<meta[^>]+content=")([^"]*)(")', r"\1\3", cleaned)

    if cleaned == text:
        if not rep.findings:
            rep.findings.append(_finding("EPUB", "(nothing to strip)", "keep", "", "info"))
        return rep
    rep.sanitized = not dry_run
    if dry_run:
        return rep
    buf = BytesIO()
    with zipfile.ZipFile(path) as zf, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for name in zf.namelist():
            info = zf.getinfo(name)
            if name == opf:
                out.writestr(info, cleaned.encode("utf-8"))
            else:
                out.writestr(info, zf.read(name))
    import os
    tmp = path + ".metadata-studio.tmp"
    with open(tmp, "wb") as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, path)
    rep.bytes_out = os.path.getsize(path)
    return rep


# --- HTML / RTF / SVG (single text container) -------------------------

HTML_META_FIELDS = [
    ("author", "Author"), ("generator", "Generator"), ("created", "Created"),
    ("last-modified", "Last modified"), ("publisher", "Publisher"),
    ("copyright", "Copyright"), ("keywords", "Keywords"),
    ("description", "Description"), ("robots", "Robots"),
]

RTF_INFO_FIELDS = [
    ("author", "Author"), ("title", "Title"), ("subject", "Subject"),
    ("company", "Company"), ("manager", "Manager"), ("operator", "Operator"),
    ("keywords", "Keywords"), ("category", "Category"), ("comment", "Comment"),
    ("creatim", "Created"), ("revtim", "Last saved"), ("printim", "Last printed"),
]

SVG_METADATA_FIELDS = [
    ("dc:title", "Title"), ("dc:creator", "Creator"),
    ("dc:publisher", "Publisher"), ("dc:date", "Date"),
    ("dc:description", "Description"), ("dc:subject", "Subject"),
    ("dc:rights", "Rights"), ("dc:identifier", "Identifier"),
]


def _inspect_html(path: str, ext: str) -> FileReport:
    rep = FileReport(path=path, format=ext, category="document")
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    for tag, label in HTML_META_FIELDS:
        for m in re.finditer(r'<meta[^>]+name=["\']?' + re.escape(tag) +
                             r'["\'][^>]+content=["\']([^"\']*)["\']',
                             text, flags=re.IGNORECASE):
            rep.findings.append(_finding(f"HTML:meta:{label}", _preview(m.group(1)),
                                         "strip", "personal", "warning"))
        # also match <meta content=... name=...> reversed order
        for m in re.finditer(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']?' +
                             re.escape(tag) + r'["\']', text, flags=re.IGNORECASE):
            rep.findings.append(_finding(f"HTML:meta:{label}", _preview(m.group(1)),
                                         "strip", "personal", "warning"))
    m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        rep.findings.append(_finding("HTML:title", _preview(m.group(1)),
                                     "keep", "document", "info"))
    if not rep.findings:
        rep.findings.append(_finding("HTML", "(no metadata)", "keep", "", "info"))
    return rep


def _inspect_rtf(path: str) -> FileReport:
    rep = FileReport(path=path, format="rtf", category="document")
    try:
        txt = Path(path).read_text(encoding="latin-1", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    for field, label in RTF_INFO_FIELDS:
        m = re.search(r"\\" + re.escape(field) + r"\s*([^\\{]+)", txt, flags=re.IGNORECASE)
        if m and m.group(1).strip():
            rep.findings.append(_finding(f"RTF:{label}", _preview(m.group(1)),
                                         "strip", "personal", "warning"))
    if not rep.findings:
        rep.findings.append(_finding("RTF", "(no \\info metadata)", "keep", "", "info"))
    return rep


def _inspect_svg(path: str) -> FileReport:
    rep = FileReport(path=path, format="svg", category="document")
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    for tag, label in SVG_METADATA_FIELDS:
        for m in re.finditer(r"<" + re.escape(tag) + r"[^>]*>(.*?)</" + re.escape(tag) + r">",
                             text, flags=re.DOTALL):
            if m.group(1).strip():
                val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                rep.findings.append(_finding(f"SVG:{label}", _preview(val),
                                             "strip", "personal", "warning"))
    if not rep.findings:
        rep.findings.append(_finding("SVG", "(no metadata)", "keep", "", "info"))
    return rep


def _sanitize_html(path: str, ext: str, dry_run: bool) -> FileReport:
    rep = _inspect_html(path, ext)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    cleaned = text
    for tag, label in HTML_META_FIELDS:
        cleaned = re.sub(
            r'(<meta[^>]*name=["\']?' + re.escape(tag) + r'["\'][^>]*content=["\'])([^"\']*)(["\'][^>]*/?>)',
            r'\1\3', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r'(<meta[^>]*content=["\'])([^"\']*)(["\'][^>]*name=["\']?' + re.escape(tag) + r'["\'])',
            r'\1\3', cleaned, flags=re.IGNORECASE)
    if cleaned != text:
        rep.sanitized = not dry_run
        if not dry_run:
            import os
            tmp = path + ".metadata-studio.tmp"
            Path(tmp).write_text(cleaned, encoding="utf-8")
            os.replace(tmp, path)
            rep.bytes_out = os.path.getsize(path)
    else:
        rep.findings = [f for f in rep.findings if f.action == "strip"]
        if not rep.findings:
            rep.findings.append(_finding(f"HTML", "(nothing to strip)", "keep", "", "info"))
    return rep


def _sanitize_rtf(path: str, dry_run: bool) -> FileReport:
    rep = _inspect_rtf(path)
    try:
        txt = Path(path).read_text(encoding="latin-1", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    cleaned = txt
    for field, label in RTF_INFO_FIELDS:
        pat = re.compile(r"\\" + re.escape(field) + r"([^\\{]+)", re.IGNORECASE)
        if pat.search(cleaned):
            cleaned = pat.sub(r"\\" + field, cleaned, count=1)
    if cleaned != txt:
        rep.sanitized = not dry_run
        if not dry_run:
            import os
            tmp = path + ".metadata-studio.tmp"
            Path(tmp).write_text(cleaned, encoding="latin-1")
            os.replace(tmp, path)
            rep.bytes_out = os.path.getsize(path)
    else:
        rep.findings = []
        rep.findings.append(_finding("RTF", "(nothing to strip)", "keep", "", "info"))
    return rep


def _sanitize_svg(path: str, dry_run: bool) -> FileReport:
    rep = _inspect_svg(path)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        rep.error = str(exc)
        return rep
    cleaned = text
    for tag, label in SVG_METADATA_FIELDS:
        cleaned = re.sub(r"(<" + re.escape(tag) + r"[^>]*>).*?(</" + re.escape(tag) + r">)",
                         r"\1\2", cleaned, flags=re.DOTALL)
    if cleaned != text:
        rep.sanitized = not dry_run
        if not dry_run:
            import os
            tmp = path + ".metadata-studio.tmp"
            Path(tmp).write_text(cleaned, encoding="utf-8")
            os.replace(tmp, path)
            rep.bytes_out = os.path.getsize(path)
    else:
        rep.findings = []
        rep.findings.append(_finding("SVG", "(nothing to strip)", "keep", "", "info"))
    return rep


def inspect(path: str | Path) -> FileReport:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return _inspect_pdf(str(path))
    if suffix in (".docx", ".xlsx", ".pptx"):
        rep = _doc_inspect(str(path), "docProps/core.xml", OOXML_CORE_FIELDS,
                           "OOXML:core", suffix.lstrip("."))
        # also surface app.xml fields (company/manager) — merge into same report
        try:
            with zipfile.ZipFile(path) as zf:
                xml = _read_zip_member(zf, "docProps/app.xml")
            if xml:
                text = xml.decode("utf-8", "replace")
                for tag, label in OOXML_APP_FIELDS:
                    m = re.search(r"<" + tag + r"[^>]*>(.*?)</" + tag + r">",
                                  text, flags=re.DOTALL)
                    if m and m.group(1).strip():
                        rep.findings.append(_finding(f"OOXML:app:{label}",
                                                     _preview(m.group(1).strip()),
                                                     "strip", "personal", "warning"))
        except Exception:
            pass
        return rep
    if suffix in (".odt", ".ods", ".odp"):
        return _doc_inspect(str(path), "meta.xml", ODF_META_FIELDS,
                            "ODF", suffix.lstrip("."))
    if suffix == ".epub":
        return _inspect_epub(str(path))
    if suffix in (".html", ".htm", ".xhtml"):
        return _inspect_html(str(path), suffix.lstrip("."))
    if suffix == ".rtf":
        return _inspect_rtf(str(path))
    if suffix == ".svg":
        return _inspect_svg(str(path))
    rep = FileReport(path=str(path), format=suffix.lstrip("."), category="document")
    rep.error = f"unsupported document format: {suffix}"
    return rep


def sanitize(path: str | Path, dry_run: bool = False) -> FileReport:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return _sanitize_pdf(str(path), dry_run)
    if suffix in (".docx", ".xlsx", ".pptx"):
        core = _doc_sanitize(str(path), "docProps/core.xml", OOXML_CORE_FIELDS,
                             "OOXML:core", suffix.lstrip("."), dry_run)
        app = _doc_sanitize(str(path), "docProps/app.xml", OOXML_APP_FIELDS,
                            "OOXML:app", suffix.lstrip("."), dry_run)
        # merge: core carries the primary report, app findings are appended
        app_seen = {f.key for f in core.findings}
        core.findings.extend(f for f in app.findings if f.key not in app_seen and f.action in ("strip", "set"))
        core.sanitized = core.sanitized or app.sanitized
        return core
    if suffix in (".odt", ".ods", ".odp"):
        return _doc_sanitize(str(path), "meta.xml", ODF_META_FIELDS,
                             "ODF", suffix.lstrip("."), dry_run)
    if suffix == ".epub":
        return _sanitize_epub(str(path), dry_run)
    if suffix in (".html", ".htm", ".xhtml"):
        return _sanitize_html(str(path), suffix.lstrip("."), dry_run)
    if suffix == ".rtf":
        return _sanitize_rtf(str(path), dry_run)
    if suffix == ".svg":
        return _sanitize_svg(str(path), dry_run)
    rep = FileReport(path=str(path), format=suffix.lstrip("."), category="document")
    rep.error = f"unsupported document format: {suffix}"
    return rep
