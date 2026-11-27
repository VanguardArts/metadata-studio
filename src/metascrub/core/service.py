"""Unified service — the single entry point for the GUI and CLI.

Dispatches each path to the right engine by category, provides batch processing
(threaded), folder recursion, before/after comparison, and optional JSON/UTF-8
report emission.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .dispatch import category_for, is_supported
from .model import CompareResult, FileReport, Finding
from ..engines import audio, document, image as _image

ProgressCb = Optional[Callable[[int, int, FileReport], None]]


def inspect(path: str | Path, **kw) -> FileReport:
    path = Path(path)
    cat = category_for(path)
    if cat == "image":
        return _image.inspect(path)
    if cat == "audio":
        return audio.inspect(path, opts=kw.get("audio_opts"))
    if cat == "document":
        return document.inspect(path)
    rep = FileReport(path=str(path), format=path.suffix.lstrip(".").lower(),
                     category="other")
    rep.error = f"unsupported file type: {path.suffix or '(none)'}"
    return rep


def sanitize(path: str | Path, level: int = 0, dry_run: bool = False, **kw) -> FileReport:
    path = Path(path)
    cat = category_for(path)
    if cat == "image":
        if dry_run:
            rep = inspect(path)
            rep.sanitized = False
            rep.findings = [f for f in rep.findings if f.action in ("strip", "flag")]
            rep.findings.append(Finding(
                key="dry-run", value=f"would strip at level {level}", action="review",
                kind="", severity="info"))
            return rep
        return _image.sanitize(path, level=level, out_format=kw.get("out_format", "auto"))
    if cat == "audio":
        return audio.sanitize(path, opts=kw.get("audio_opts"), dry_run=dry_run)
    if cat == "document":
        return document.sanitize(path, dry_run=dry_run)
    rep = FileReport(path=str(path), format=path.suffix.lstrip(".").lower(),
                     category="other")
    rep.error = f"unsupported file type: {path.suffix or '(none)'}"
    return rep


def verify(path: str | Path, **kw) -> FileReport:
    path = Path(path)
    cat = category_for(path)
    if cat == "audio":
        return audio.verify(path, opts=kw.get("audio_opts"))
    # images: re-inspect and keep only findings that would be stripped
    rep = inspect(path)
    rep.findings = [f for f in rep.findings if f.action in ("strip", "flag")]
    return rep


def _iter_files(paths: Iterable[str | Path], recurse: bool = False) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            if is_supported(p):
                out.append(p)
        elif p.is_dir() and recurse:
            out.extend(sorted(q for q in p.rglob("*") if q.is_file() and is_supported(q)))
    return out


def batch_inspect(paths, recurse: bool = False, workers: Optional[int] = None,
                  progress: ProgressCb = None, **kw) -> List[FileReport]:
    files = _iter_files(paths, recurse)
    return _run(files, lambda f: inspect(f, **kw), workers, progress)


def batch_sanitize(paths, recurse: bool = False, level: int = 0, dry_run: bool = False,
                   workers: Optional[int] = None, progress: ProgressCb = None,
                   **kw) -> List[FileReport]:
    files = _iter_files(paths, recurse)
    return _run(files, lambda f: sanitize(f, level=level, dry_run=dry_run, **kw),
                workers, progress)


def batch_verify(paths, recurse: bool = False, workers: Optional[int] = None,
                 progress: ProgressCb = None, **kw) -> List[FileReport]:
    files = _iter_files(paths, recurse)
    return _run(files, lambda f: verify(f, **kw), workers, progress)


def _run(files, fn, workers, progress) -> List[FileReport]:
    if workers is None:
        workers = min(8, os.cpu_count() or 2)
    workers = max(1, min(workers, len(files) or 1))
    results: List[FileReport] = []
    done = 0
    if workers == 1 or len(files) <= 1:
        for f in files:
            res = fn(f)
            results.append(res)
            done += 1
            if progress:
                progress(done, len(files), res)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fn, f): f for f in files}
            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                done += 1
                if progress:
                    progress(done, len(files), res)
    results.sort(key=lambda r: r.path)
    return results


def compare(before: FileReport, after: FileReport) -> CompareResult:
    return CompareResult(path=before.path, before=before, after=after)
