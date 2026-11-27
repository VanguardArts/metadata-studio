"""Command-line interface for Metascrub.

Mirrors the Audio Scrub CLI shape (scan / clean / verify) but is format-agnostic:
it dispatches to the image, audio, and document engines by file type.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .core import service
from .engines.audio import AudioOptions, Credits


def _audio_opts(args) -> Optional[AudioOptions]:
    has_credit = any(getattr(args, a, None) for a in
                     ("artist", "album", "year", "composer", "label", "copyright",
                      "title", "genre"))
    if not has_credit and not getattr(args, "audio", False):
        return None
    return AudioOptions(
        credits=Credits(
            title=getattr(args, "title", None),
            artist=getattr(args, "artist", None),
            album=getattr(args, "album", None),
            year=getattr(args, "year", None),
            genre=getattr(args, "genre", None),
            composer=getattr(args, "composer", None),
            label=getattr(args, "label", None),
            copyright=getattr(args, "copyright", None),
        ),
        remove_cover_art=not getattr(args, "keep_cover_art", False),
        remove_unset_credits=getattr(args, "remove_unset_credits", False),
        extra_signatures=getattr(args, "signature", []) or [],
    )


def _add_common(p):
    p.add_argument("path", help="File or folder tree to process.")
    p.add_argument("--json", action="store_true", help="Emit JSON.")
    p.add_argument("--workers", type=int, default=None,
                   help="Parallel worker count (default: min(8, CPU count)).")
    p.add_argument("--exclude", action="append", default=[],
                   help="Regex (relpath) to skip (repeatable).")


def _build_parser():
    ap = argparse.ArgumentParser(prog="metascrub",
                                 description="Metascrub — unified metadata inspect/clean/verify.")
    ap.add_argument("--version", action="version", version=f"metascrub {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scan", help="Inspect metadata without modifying.")
    _add_common(sp)

    cp = sub.add_parser("clean", help="Strip metadata (and set credits).")
    _add_common(cp)
    cp.add_argument("--apply", action="store_true",
                    help="Actually write changes (default is a dry run).")
    cp.add_argument("--level", type=int, default=0, choices=[0, 1, 2, 3],
                    help="Image transform ladder level (0=lossless strip .. 3).")
    cp.add_argument("--artist", help="Credit: artist.")
    cp.add_argument("--album", help="Credit: album/release.")
    cp.add_argument("--year", help="Credit: year.")
    cp.add_argument("--genre", help="Credit: genre.")
    cp.add_argument("--composer", help="Credit: composer/production.")
    cp.add_argument("--label", help="Credit: label/publisher.")
    cp.add_argument("--copyright", help="Credit: copyright line.")
    cp.add_argument("--title", help="Credit: title.")
    cp.add_argument("--keep-cover-art", action="store_true",
                    help="Keep embedded cover art (audio).")
    cp.add_argument("--remove-unset-credits", action="store_true",
                    help="Evict credit tags even without a replacement value.")
    cp.add_argument("--signature", action="append", default=[],
                    help="Extra provenance signature to hunt (repeatable).")

    vp = sub.add_parser("verify", help="Fail if any provenance signature remains.")
    _add_common(vp)

    return ap


def _emit(results, json_mode, dry_run):
    if json_mode:
        print(json.dumps({"dry_run": dry_run,
                          "files": [r.as_dict() for r in results]}, indent=2))
        return
    for r in results:
        print(f"{r.path}  [{r.format}]" + ("  SKIP" if r.skipped else "")
              + (f"  ERR: {r.error}" if r.error else ""))
        for f in r.findings:
            marker = {"strip": "-", "set": "+", "keep": "=",
                      "flag": "!", "review": "?"}.get(f.action, "?")
            print(f"  {marker} {f.key:<24} [{f.action}]  {f.value}")
    total = sum(len(r.findings) for r in results)
    nstrip = sum(1 for r in results for f in r.findings if f.action == "strip")
    print(f"\nSummary: {len(results)} files, {nstrip} findings strip, {total} total.")
    if dry_run:
        print("DRY RUN — no files modified. Re-run with --apply to write.")


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    opts = _audio_opts(args)
    kw = {"audio_opts": opts}

    if args.command == "scan":
        results = service.batch_inspect([args.path], recurse=True,
                                        workers=args.workers, **kw)
        _emit(results, args.json, dry_run=True)
        return 0

    if args.command == "clean":
        dry = not args.apply
        results = service.batch_sanitize(
            [args.path], recurse=True, level=args.level, dry_run=dry,
            workers=args.workers, **kw)
        _emit(results, args.json, dry_run=dry)
        return 2 if any(r.error for r in results) else 0

    if args.command == "verify":
        results = service.batch_verify([args.path], recurse=True, workers=args.workers, **kw)
        hits = sum(len(r.findings) for r in results)
        if args.json:
            _emit(results, True, dry_run=True)
        else:
            for r in results:
                for f in r.findings:
                    print(f"HIT {r.path}: {f.key} = {f.value}")
            print("verify: OK — no provenance signatures found." if hits == 0
                  else f"verify: FAILED — {hits} provenance signature(s) remain.")
        return 1 if hits else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
