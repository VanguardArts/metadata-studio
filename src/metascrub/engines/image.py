"""Image engine — EXIF / XMP / IPTC / C2PA detection and stripping.

Adapted from Image Scrub's proven chunk/marker-surgery techniques:

* PNG  — ancillary chunk surgery (drop caBX/C2PA, eXIf, text, tIME), keep
         critical + color-management chunks. Pixel-lossless.
* JPEG — marker surgery (drop APP1/APP11/APP13/COM and non-essential APPn),
         keep entropy-coded data verbatim. Pixel-lossless.
* WebP — RIFF chunk surgery (drop EXIF/XMP).
* Other/TIFF/BMP — Pillow decode + clean re-encode.

The ``sanitize`` transform ladder is identical in spirit to image-scrub:
level 0 = metadata strip only (lossless); 1 = clean re-encode (JPEG 97);
2 = q90 + resample x0.97 + faint noise; 3 = micro-crop + resample + jitter +
noise + q88.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

from ..core.dispatch import category_for
from ..core.model import FileReport, Finding
from . import _finding

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_CRITICAL = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
PNG_COLOR_KEEP = {b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"sBIT", b"pHYs"}

# heuristic byte signatures worth flagging (report-only)
BYTE_SIGNATURES = [
    (b"c2pa", "byte signature: C2PA reference"),
    (b"jumbf", "byte signature: JUMBF container"),
    (b"jumb", "byte signature: JUMBF box"),
    (b"<x:xmpmeta", "byte signature: XMP packet"),
    (b"xpacket begin", "byte signature: XMP packet"),
    (b"Photoshop 3.0", "byte signature: IPTC (Photoshop)"),
    (b"adobe", "byte signature: Adobe resource"),
    (b"SynthID", "byte signature: SynthID reference"),
    (b"trainedAlgorithmicMedia", "byte signature: trained algorithmic media"),
]

_LEVELS = (0, 1, 2, 3)


def _preview(v, limit: int = 80) -> str:
    s = " ".join(str(v).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


# --- detection ---------------------------------------------------------

def _detect_png(data: bytes, rep: FileReport) -> None:
    off = 8
    while off + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[off : off + 8])
        name = ctype.decode("latin1", "replace")
        if ctype == b"caBX":
            rep.findings.append(_finding(f"PNG:caBX", f"{length} bytes",
                                         "strip", "provenance", "critical"))
        elif ctype == b"eXIf":
            rep.findings.append(_finding("PNG:eXIf", f"{length} bytes",
                                         "strip", "personal", "warning"))
        elif ctype in (b"tEXt", b"iTXt", b"zTXt"):
            payload = data[off + 8 : off + 8 + length]
            kw = payload.split(b"\x00", 1)[0].decode("latin1", "replace")
            val = payload.split(b"\x00", 1)[1][:80] if b"\x00" in payload else b""
            rep.findings.append(_finding(f"PNG:{name}", _preview(val),
                                         "strip", "tag", "warning"))
        elif ctype == b"tIME":
            rep.findings.append(_finding("PNG:tIME", f"{length} bytes",
                                         "strip", "tag", "warning"))
        elif ctype == b"fThN":
            rep.findings.append(_finding("PNG:fThN", f"{length} bytes",
                                         "strip", "provenance", "critical"))
        off += 12 + length
        if ctype == b"IEND":
            break


def _detect_jpeg(data: bytes, rep: FileReport) -> None:
    off = 2
    while off + 4 <= len(data):
        if data[off] != 0xFF:
            break
        marker = data[off + 1]
        if marker == 0xD8 or marker == 0x01 or (0xD0 <= marker <= 0xD7):
            off += 2
            continue
        length = struct.unpack(">H", data[off + 2 : off + 4])[0]
        body = data[off + 4 : off + 2 + length]
        name = marker - 0xE0
        label = {1: "EXIF/XMP (APP1)", 11: "JUMBF/C2PA (APP11)",
                 13: "IPTC (APP13)", 0xFE: "COM"}.get(name, f"APP{name}")
        sev = "critical" if name in (1, 11) else "warning"
        rep.findings.append(_finding(f"JPEG:APP{name}", f"{length} bytes",
                                     "strip", "provenance", sev))
        # surface XMP/IPTC presence from body
        if b"<x:xmpmeta" in body or b"xpacket begin" in body:
            rep.findings.append(_finding("JPEG:XMP", "XMP packet",
                                         "strip", "provenance", "warning"))
        if b"Photoshop 3.0" in body:
            rep.findings.append(_finding("JPEG:IPTC", "IPTC resource",
                                         "strip", "personal", "warning"))
        off += 2 + length
        if marker == 0xDA:  # start of scan — pixel data begins
            break


def _detect_webp(data: bytes, rep: FileReport) -> None:
    off = 12
    while off + 8 <= len(data):
        ctype = data[off : off + 4]
        length = struct.unpack("<I", data[off + 4 : off + 8])[0]
        name = ctype.decode("latin1", "replace")
        if ctype in (b"EXIF", b"XMP "):
            rep.findings.append(_finding(f"WebP:{name}", f"{length} bytes",
                                         "strip", "provenance", "critical"))
        off += 8 + length + (length & 1)


def inspect(path: str | Path) -> FileReport:
    path = Path(path)
    data = path.read_bytes()
    rep = FileReport(path=str(path), format=path.suffix.lstrip(".").lower(),
                     category="image")

    if data.startswith(PNG_SIGNATURE):
        _detect_png(data, rep)
    elif data.startswith(b"\xff\xd8\xff"):
        _detect_jpeg(data, rep)
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        _detect_webp(data, rep)
    else:
        rep.format = rep.format or "other"

    # EXIF via Pillow (authoritative key/value view)
    try:
        with Image.open(io.BytesIO(data)) as im:
            exif = im.getexif()
            for tag_id, value in exif.items():
                key = f"EXIF:{tag_id}"
                val = f"<{len(value)} bytes>" if isinstance(value, bytes) else _preview(value)
                rep.findings.append(_finding(key, val, "strip", "personal", "warning"))
            xmp = im.getxmp()
            if xmp and "xmp" in xmp:
                rep.findings.append(_finding("XMP", _preview(xmp["xmp"], 120),
                                             "strip", "provenance", "critical"))
    except Exception:
        pass

    # heuristic byte-signature scan (report-only)
    for sig, label in BYTE_SIGNATURES:
        if sig in data:
            rep.findings.append(_finding("bytes:" + sig.decode("latin1", "replace"),
                                         label, "flag", "provenance", "warning"))

    return rep


# --- sanitize ----------------------------------------------------------

def _strip_png(data: bytes) -> bytes:
    out = bytearray(data[:8])
    off = 8
    while off + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[off : off + 8])
        seg = data[off : off + 12 + length]
        if ctype in PNG_CRITICAL or ctype in PNG_COLOR_KEEP:
            out += seg
        off += 12 + length
        if ctype == b"IEND":
            break
    if not out.endswith(b"IEND\xaeB`\x82"):
        raise ValueError("PNG: IEND not found, file may be truncated")
    return bytes(out)


_JPEG_KEEP_APP = {0xE0, 0xEE}
_JPEG_KEEP_OTHER = {0xC0, 0xC1, 0xC2, 0xC4, 0xC8, 0xCC, 0xDB, 0xDD}


def _strip_jpeg(data: bytes) -> bytes:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("JPEG: missing SOI")
    out = bytearray(data[:2])
    off = 2
    while off + 4 <= len(data):
        if data[off] != 0xFF:
            break
        marker = data[off + 1]
        if marker == 0xD8 or marker == 0x01 or (0xD0 <= marker <= 0xD7):
            out += data[off : off + 2]
            off += 2
            continue
        length = struct.unpack(">H", data[off + 2 : off + 4])[0]
        seg = data[off : off + 2 + length]
        if marker == 0xDA:  # start of scan: copy everything verbatim
            out += data[off:]
            break
        if marker in _JPEG_KEEP_OTHER or marker in _JPEG_KEEP_APP:
            out += seg
        off += 2 + length
    return bytes(out)


def _strip_webp(data: bytes) -> bytes:
    out = bytearray(data[:12])
    off = 12
    while off + 8 <= len(data):
        ctype = data[off : off + 4]
        length = struct.unpack("<I", data[off + 4 : off + 8])[0]
        seg = data[off : off + 8 + length + (length & 1)]
        if ctype not in (b"EXIF", b"XMP "):
            out += seg
        off += 8 + length + (length & 1)
    return bytes(out)


def _strip_fallback(src: Path) -> bytes:
    buf = io.BytesIO()
    with Image.open(src) as im:
        fmt = im.format or "PNG"
        if fmt in ("JPEG",):
            im.convert("RGB").save(buf, "JPEG", quality=97)
        elif fmt == "WEBP":
            im.save(buf, "WEBP", lossless=True)
        else:
            im.convert("RGB").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def strip_bytes(src: Path) -> tuple[bytes, str]:
    data = src.read_bytes()
    if data.startswith(PNG_SIGNATURE):
        return _strip_png(data), "png-chunk-surgery"
    if data.startswith(b"\xff\xd8\xff"):
        return _strip_jpeg(data), "jpeg-marker-surgery"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return _strip_webp(data), "webp-riff-surgery"
    return _strip_fallback(src), "reencode-fallback"


def _psnr(a: Image.Image, b: Image.Image) -> float:
    import math

    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    hist = diff.histogram()
    sq = sum(value * ((i % 256) ** 2) for i, value in enumerate(hist))
    n = a.size[0] * a.size[1] * 3
    mse = sq / n
    if mse == 0:
        return float("inf")
    return 10 * math.log10(255.0**2 / mse)


def _encode(im: Image.Image, out_format: str, quality) -> bytes:
    buf = io.BytesIO()
    if out_format == "JPEG":
        im.convert("RGB").save(buf, "JPEG", quality=quality or 95,
                               subsampling=1, optimize=True)
    elif out_format == "WEBP":
        im.save(buf, "WEBP", quality=quality or 95, method=6)
    else:
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _resample(im: Image.Image, factor: float) -> Image.Image:
    w, h = im.size
    small = im.resize((max(1, round(w * factor)), max(1, round(h * factor))),
                      Image.LANCZOS)
    return small.resize((w, h), Image.LANCZOS)


def _noise(im: Image.Image, sigma: float) -> Image.Image:
    src = im.convert("RGB")
    gray = Image.effect_noise(src.size, max(1.0, sigma * 4))
    delta = gray.point(lambda p: p - 128)
    delta_rgb = Image.merge("RGB", (delta, delta, delta))
    return ImageChops.add(src, delta_rgb)


def _color_jitter(im: Image.Image, pct: float, seed: int) -> Image.Image:
    import random

    rnd = random.Random(seed)
    im = ImageEnhance.Contrast(im).enhance(1 + rnd.uniform(-pct, pct))
    im = ImageEnhance.Brightness(im).enhance(1 + rnd.uniform(-pct, pct))
    im = ImageEnhance.Color(im).enhance(1 + rnd.uniform(-pct, pct))
    return im


def _micro_crop(im: Image.Image, max_px: int, seed: int) -> Image.Image:
    import random

    rnd = random.Random(seed)
    w, h = im.size
    l, t = rnd.randint(0, max_px), rnd.randint(0, max_px)
    r, b = rnd.randint(0, max_px), rnd.randint(0, max_px)
    cropped = im.crop((l, t, w - r, h - b))
    return cropped.resize((w, h), Image.LANCZOS)


def sanitize(path: str | Path, level: int = 0, out_format: str = "auto") -> FileReport:
    if level not in _LEVELS:
        raise ValueError(f"level must be one of {_LEVELS}")
    src = Path(path)
    rep = FileReport(path=str(src), format=src.suffix.lstrip(".").lower(),
                     category="image", bytes_in=src.stat().st_size)
    seed = hash(src.name) & 0xFFFF

    clean, method = strip_bytes(src)
    if level == 0:
        blob = clean
        ext = src.suffix.lstrip(".").lower() or "png"
        psnr = float("inf")
    else:
        src_im = Image.open(io.BytesIO(clean))
        src_im.load()
        src_im = src_im.convert("RGB")
        fmt = out_format
        if fmt == "auto":
            fmt = "JPEG"
        elif fmt == "same":
            fmt = "PNG" if src.suffix.lower() == ".png" else "JPEG"

        im = src_im
        if level == 1:
            blob = _encode(im, fmt, 97)
        elif level == 2:
            im = _resample(im, 0.97)
            im = _noise(im, 0.8)
            blob = _encode(im, fmt, 90)
        else:
            im = _micro_crop(im, 2, seed)
            im = _resample(im, 0.96)
            im = _color_jitter(im, 0.015, seed)
            im = _noise(im, 1.2)
            blob = _encode(im, fmt, 88)

        result = Image.open(io.BytesIO(blob))
        result.load()
        psnr = _psnr(src_im, result.convert("RGB"))
        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]

    rep.sanitized = True
    rep.bytes_out = len(blob)
    rep.psnr_db = None if psnr == float("inf") else round(psnr, 2)
    rep.findings.append(_finding(f"engine", f"{method} → {ext}", "keep",
                                 "", "info"))
    rep._blob = blob          # internal: caller writes bytes
    rep._ext = ext
    return rep
