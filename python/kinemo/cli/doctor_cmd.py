"""`kinemo doctor`: what kinemo finds on this machine, to check a setup and to paste into
bug reports."""

from __future__ import annotations

import argparse
import os
import platform

from .environment import ffmpeg_install_hint, find_ffmpeg, has_module, python_version


def _line(label: str, value: str, ok: bool = True) -> str:
    return f"  {'✓' if ok else '✗'} {label:<14} {value}"


def run(args: argparse.Namespace) -> int:
    import kinemo

    from .. import _core
    from ..project import find_root

    print(f"kinemo {kinemo.__version__} (IR {kinemo.IR_VERSION})")
    lines = [
        _line("python", python_version()),
        _line("platform", f"{platform.system()} {platform.release()} ({platform.machine()})"),
    ]
    ffmpeg = find_ffmpeg()
    if ffmpeg.path is not None:
        lines.append(_line("ffmpeg", f"{ffmpeg.version} ({ffmpeg.path})"))
    else:
        lines.append(_line("ffmpeg", f"not found: {ffmpeg.problem}; install: {ffmpeg_install_hint()}", ok=False))
    lines.append(_line("native core", os.path.basename(_core.__file__ or "built in")))
    gpu = getattr(_core, "gpu_available", None)
    if callable(gpu):
        lines.append(_line("gpu preview", "available" if gpu() else "no adapter (the CPU renders the preview)"))
    lines.append(_line("align extra", "installed" if has_module("faster_whisper") else 'not installed (pip install "kinemo[align]" for word timing)'))
    root = find_root(os.getcwd())
    lines.append(_line("project", os.path.join(root, "kinemo.toml") if root else "no kinemo.toml from here upwards (defaults apply)"))
    print("\n".join(lines))
    # A missing ffmpeg is the only thing that stops renders.
    return 0 if ffmpeg.path is not None else 1
