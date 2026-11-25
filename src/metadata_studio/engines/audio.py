"""Audio engine — ID3 (MP3) and RIFF (WAV) metadata hygiene.

Adapted from Metascrub: byte-safe (never re-encodes audio), dry-run aware,
atomic writes, and verifies the audio payload is unchanged after a rewrite.

Supports the provenance evidence Metascrub strips by default: generator
comments, unsynced lyrics, origin URLs, C2PA manifests (MP3 `GEOB` / WAV
`C2PA` chunk), encoder fingerprints, private/watermark frames, and embedded
cover art.
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from ..core.model import FileReport, Finding
from . import _finding

# --- default strip lists (mirror metascrub) ----------------------------

DEFAULT_STRIP_ID3_FRAMES = [
    "COMM",   # comments ("made with ...", ids)
    "USLT",   # unsynced lyrics
    "SYLT",   # synchronised lyrics
    "GEOB",   # general encapsulated object (C2PA manifest store)
    "WOAS",   # official audio source webpage
    "WXXX",   # user-defined URL frames
    "TSSE",   # software/encoder fingerprint (Lavf...)
    "TENC",   # encoded-by
    "TXXX",   # user-defined text (major_brand/minor_version/...)
    "PRIV",   # private frames (watermark/owner ids)
]

DEFAULT_STRIP_RIFF_CHUNKS = ["C2PA"]
DEFAULT_STRIP_RIFF_INFO = ["ICMT", "ISFT"]

DEFAULT_SIGNATURES = [
    "suno", "udio", "stable audio", "mubert", "boomy", "aiva", "soundraw",
    "made with", "c2pa", "content credentials", "lavf",
]

# MP3 credit mapping: frame id -> (label, credit attr)
ID3_CREDIT_ORDER = [
    ("TIT2", "title"),
    ("TPE1", "artist"),
    ("TPE2", "album_artist"),
    ("TALB", "album"),
    ("TDRC", "year"),
    ("TCON", "genre"),
    ("TCOM", "composer"),
    ("TPUB", "label"),
    ("TCOP", "copyright"),
]

WAV_INFO_ORDER = ["INAM", "IART", "IPRD", "ICRD", "IGNR", "ICOP", "IENG"]


@dataclass
class Credits:
    title: Optional[str] = None
    artist: Optional[str] = None
    album_artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    composer: Optional[str] = None
    label: Optional[str] = None
    copyright: Optional[str] = None


@dataclass
class AudioOptions:
    credits: Credits = field(default_factory=Credits)
    remove_cover_art: bool = True
    remove_unset_credits: bool = False
    strip_id3_frames: List[str] = field(default_factory=lambda: list(DEFAULT_STRIP_ID3_FRAMES))
    strip_riff_chunks: List[str] = field(default_factory=lambda: list(DEFAULT_STRIP_RIFF_CHUNKS))
    strip_riff_info: List[str] = field(default_factory=lambda: list(DEFAULT_STRIP_RIFF_INFO))
    extra_signatures: List[str] = field(default_factory=list)

    def signatures(self) -> List[str]:
        return [s.lower() for s in DEFAULT_SIGNATURES + self.extra_signatures]

    def matches_signature(self, text: str) -> bool:
        t = text.lower()
        return any(s in t for s in self.signatures())


def _matches_any(value, sigs):
    v = value.lower()
    return any(s in v for s in sigs)


# --- MP3 (ID3 via mutagen) --------------------------------------------

def _inspect_id3(path: str, opts: AudioOptions) -> FileReport:
    from mutagen.id3 import APIC, ID3, ID3NoHeaderError

    rep = FileReport(path=path, format="mp3", category="audio")
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    except Exception as exc:
        rep.error = str(exc)
        return rep

    for key in sorted(tags.keys()):
        frame = tags[key]
        value = _preview_frame(frame)
        if key.startswith("APIC"):
            action = "strip" if opts.remove_cover_art else "keep"
            rep.findings.append(_finding(f"ID3:{key}", value, action, "personal", "warning"))
        elif any(key.startswith(p) for p in opts.strip_id3_frames):
            rep.findings.append(_finding(f"ID3:{key}", value, "strip", "provenance", "critical"))
        elif _matches_any(value, opts.signatures()):
            rep.findings.append(_finding(f"ID3:{key}", value, "flag", "tag", "critical"))
        else:
            rep.findings.append(_finding(f"ID3:{key}", value, "keep", "tag", "info"))

    if not tags:
        rep.findings.append(_finding("ID3", "(no ID3 tag)", "keep", "tag", "info"))
    return rep


def _preview_frame(frame) -> str:
    from mutagen.id3 import APIC

    if isinstance(frame, APIC):
        return f"{frame.mime} ({len(frame.data)} bytes)"
    url = getattr(frame, "url", None)
    if url:
        return _preview(url)
    text = getattr(frame, "text", None)
    if isinstance(text, list):
        return _preview(";".join(str(t) for t in text))
    if text is not None:
        return _preview(text)
    data = getattr(frame, "data", None)
    if data is not None:
        return f"{getattr(frame, 'mime', '?')} ({len(data)} bytes)"
    return _preview(str(frame))


def _preview(text, limit: int = 80) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _sanitize_id3(path: str, opts: AudioOptions, dry_run: bool) -> FileReport:
    from mutagen.id3 import (
        APIC, ID3, ID3NoHeaderError, TALB, TCOM, TCON, TCOP,
        TDRC, TIT2, TPE1, TPE2, TPUB,
    )

    rep = FileReport(path=path, format="mp3", category="audio")
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    except Exception as exc:
        rep.error = str(exc)
        return rep

    c = opts.credits
    to_set = [
        ("TIT2", TIT2, c.title),
        ("TPE1", TPE1, c.artist),
        ("TPE2", TPE2, c.album_artist or c.artist),
        ("TALB", TALB, c.album),
        ("TDRC", TDRC, c.year),
        ("TCON", TCON, c.genre),
        ("TCOM", TCOM, c.composer),
        ("TPUB", TPUB, c.label),
        ("TCOP", TCOP, c.copyright),
    ]
    replace_ids = {fid for fid, _, v in to_set if v is not None}
    if opts.remove_unset_credits:
        replace_ids |= {"TIT2", "TPE1", "TPE2", "TALB", "TDRC", "TCON",
                        "TCOM", "TPUB", "TCOP"}
    to_set = [(fid, cls, v) for fid, cls, v in to_set if v is not None]

    for key in list(tags.keys()):
        if key.startswith("APIC"):
            if opts.remove_cover_art:
                rep.findings.append(_finding(f"ID3:{key}", "strip", "strip", "personal", "warning"))
                del tags[key]
            else:
                rep.findings.append(_finding(f"ID3:{key}", "keep", "keep", "tag", "info"))
        elif any(key.startswith(p) for p in opts.strip_id3_frames) or key in replace_ids:
            rep.findings.append(_finding(f"ID3:{key}", "strip", "strip", "provenance", "critical"))
            del tags[key]
        else:
            rep.findings.append(_finding(f"ID3:{key}", "keep", "keep", "tag", "info"))

    for frame_id, cls, value in to_set:
        tags.add(cls(encoding=3, text=[value]))
        rep.findings.append(_finding(f"ID3:{frame_id}", _preview(value), "set", "tag", "info"))

    if dry_run:
        return rep
    tags.save(path)
    rep.sanitized = True
    rep.bytes_out = os.path.getsize(path)
    return rep


# --- WAV (RIFF) --------------------------------------------------------

def _parse_chunks(data: bytes) -> List[Tuple[bytes, bytes]]:
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    chunks = []
    pos, end = 12, len(data)
    while pos + 8 <= end:
        cid = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        body = data[pos + 8: pos + 8 + size]
        chunks.append((cid, body))
        pos += 8 + size + (size & 1)
    return chunks


def _parse_info(body: bytes) -> List[Tuple[str, str]]:
    if body[:4] != b"INFO":
        return []
    out = []
    pos = 4
    while pos + 8 <= len(body):
        code = body[pos:pos + 4].decode("latin-1")
        size = struct.unpack_from("<I", body, pos + 4)[0]
        text = body[pos + 8: pos + 8 + size].rstrip(b"\x00").decode("utf-8", "replace")
        out.append((code, text))
        pos += 8 + size + (size & 1)
    return out


def _inspect_wav(path: str, opts: AudioOptions) -> FileReport:
    rep = FileReport(path=path, format="wav", category="audio")
    try:
        with open(path, "rb") as fh:
            chunks = _parse_chunks(fh.read())
    except Exception as exc:
        rep.error = str(exc)
        return rep
    for cid, body in chunks:
        cid_s = cid.decode("latin-1").strip("\x00 ")
        if cid == b"LIST" and body[:4] == b"INFO":
            for code, text in _parse_info(body):
                if code in opts.strip_riff_info:
                    rep.findings.append(_finding(f"INFO:{code}", _preview(text), "strip", "provenance", "critical"))
                elif opts.matches_signature(text):
                    rep.findings.append(_finding(f"INFO:{code}", _preview(text), "flag", "tag", "critical"))
                else:
                    rep.findings.append(_finding(f"INFO:{code}", _preview(text), "keep", "tag", "info"))
        else:
            strip = cid_s in opts.strip_riff_chunks or cid_s in opts.strip_riff_chunks
            action = "strip" if strip else "keep"
            kind = "provenance" if strip else "audio"
            sev = "critical" if strip else "info"
            rep.findings.append(_finding(f"chunk:{cid_s}", f"{len(body)} bytes", action, kind, sev))
    return rep


_WAV_INFO_MAP = [("INAM", "title"), ("IART", "artist"), ("IPRD", "album"),
                 ("ICRD", "year"), ("IGNR", "genre"), ("ICOP", "copyright"),
                 ("IENG", "composer")]


def _build_info(fields, kept) -> bytes:
    def enc(code, text):
        b = text.encode("utf-8") + b"\x00"
        if len(b) % 2:
            b += b"\x00"
        return code.encode("ascii") + struct.pack("<I", len(b)) + b
    ordered = sorted(fields, key=lambda kv: WAV_INFO_ORDER.index(kv[0])
                     if kv[0] in WAV_INFO_ORDER else len(WAV_INFO_ORDER))
    kept_codes = {code for code, _ in fields}
    merged = ordered + [(c, v) for c, v in kept if c not in kept_codes]
    return b"INFO" + b"".join(enc(c, v) for c, v in merged)


def _assemble(chunks) -> bytes:
    out = bytearray(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    for cid, body in chunks:
        out += cid + struct.pack("<I", len(body)) + body
        if len(body) % 2:
            out += b"\x00"
    out[4:8] = struct.pack("<I", len(out) - 8)
    return bytes(out)


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _sanitize_wav(path: str, opts: AudioOptions, dry_run: bool) -> FileReport:
    rep = FileReport(path=path, format="wav", category="audio")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        chunks = _parse_chunks(data)
    except Exception as exc:
        rep.error = str(exc)
        return rep

    c = opts.credits
    strip_chunks = {x.encode("ascii") for x in opts.strip_riff_chunks}
    strip_info = set(opts.strip_riff_info)

    credit_fields = []
    for code, attr in _WAV_INFO_MAP:
        if getattr(c, attr):
            credit_fields.append((code, getattr(c, attr)))
    credit_codes = {code for code, _ in credit_fields}

    new_chunks = []
    list_seen = False
    for cid, body in chunks:
        if cid == b"LIST" and body[:4] == b"INFO":
            list_seen = True
            kept = []
            for code, text in _parse_info(body):
                if code in strip_info or code in credit_codes:
                    rep.findings.append(_finding(f"INFO:{code}", _preview(text), "strip", "provenance", "critical" if code in strip_info else "tag" if code in credit_codes else "tag", "critical"))
                else:
                    kept.append((code, text))
            merged = _build_info(credit_fields, kept)
            for code, text in credit_fields:
                rep.findings.append(_finding(f"INFO:{code}", _preview(text), "set", "tag", "info"))
            if merged:
                new_chunks.append((b"LIST", merged))
            continue
        cid_s = cid.decode("latin-1").strip("\x00 ")
        if cid in strip_chunks or cid_s in opts.strip_riff_chunks:
            rep.findings.append(_finding(f"chunk:{cid_s}", f"{len(body)} bytes", "strip", "provenance", "critical"))
            continue
        rep.findings.append(_finding(f"chunk:{cid_s}", f"{len(body)} bytes", "keep", "audio", "info"))
        new_chunks.append((cid, body))

    if not list_seen and credit_fields:
        merged = _build_info(credit_fields, [])
        for code, text in credit_fields:
            rep.findings.append(_finding(f"INFO:{code}", _preview(text), "set", "tag", "info"))
        # insert LIST after fmt; fallback to front
        inserted = False
        ordered = []
        for cid, body in new_chunks:
            if not inserted and cid == b"fmt ":
                ordered.append((b"LIST", merged))
                inserted = True
            ordered.append((cid, body))
        if not inserted:
            ordered.insert(0, (b"LIST", merged))
        new_chunks = ordered

    if dry_run:
        return rep

    audio_before = {cid: _sha(body) for cid, body in chunks if cid in (b"fmt ", b"data")}
    blob = _assemble(new_chunks)
    audio_after = {cid: _sha(body) for cid, body in _parse_chunks(blob) if cid in (b"fmt ", b"data")}
    if audio_before != audio_after:
        rep.error = "audio payload changed — refusing to write (safety check)"
        return rep
    tmp = path + ".metascrub.tmp"
    with open(tmp, "wb") as fh:
        fh.write(blob)
    os.replace(tmp, path)
    rep.sanitized = True
    rep.bytes_out = os.path.getsize(path)
    return rep


# --- public interface --------------------------------------------------

def inspect(path: str | Path, opts: Optional[AudioOptions] = None) -> FileReport:
    opts = opts or AudioOptions()
    suffix = Path(path).suffix.lower()
    if suffix == ".mp3":
        return _inspect_id3(str(path), opts)
    if suffix == ".wav":
        return _inspect_wav(str(path), opts)
    rep = FileReport(path=str(path), format=suffix.lstrip("."), category="audio")
    rep.error = f"unsupported audio format: {suffix}"
    return rep


def sanitize(path: str | Path, opts: Optional[AudioOptions] = None,
             dry_run: bool = False) -> FileReport:
    opts = opts or AudioOptions()
    suffix = Path(path).suffix.lower()
    if suffix == ".mp3":
        return _sanitize_id3(str(path), opts, dry_run)
    if suffix == ".wav":
        return _sanitize_wav(str(path), opts, dry_run)
    rep = FileReport(path=str(path), format=suffix.lstrip("."), category="audio")
    rep.error = f"unsupported audio format: {suffix}"
    return rep


def verify(path: str | Path, opts: Optional[AudioOptions] = None) -> FileReport:
    """Re-scan and return only findings matching a provenance signature."""
    opts = opts or AudioOptions()
    sigs = opts.signatures()
    rep = inspect(path, opts)
    rep.findings = [f for f in rep.findings
                    if any(s in f"{f.key} {f.value}".lower() for s in sigs)]
    return rep
