"""What kinemo needs from the machine (ffmpeg, optional extras), with install hints for the
user's system: used by `kinemo render` before it starts and by `kinemo doctor`."""

from __future__ import annotations

import importlib.util
import platform
import subprocess
import sys
from dataclasses import dataclass


class MissingFfmpeg(Exception):
    """Video output needs ffmpeg and it was not found; the message says how to install it."""


@dataclass(frozen=True)
class Ffmpeg:
    path: str | None
    version: str | None
    #: Why it was not found (or does not run), when `path` is None.
    problem: str | None


def _linux_distribution() -> str:
    try:
        with open("/etc/os-release", encoding="utf-8") as fh:
            fields = dict(line.rstrip().split("=", 1) for line in fh if "=" in line)
    except OSError:
        return ""
    return " ".join((fields.get("ID", ""), fields.get("ID_LIKE", ""))).replace('"', "").lower()


def ffmpeg_install_hint() -> str:
    """The command that installs ffmpeg on this system."""
    system = platform.system()
    if system == "Darwin":
        return "brew install ffmpeg"
    if system == "Windows":
        return "winget install Gyan.FFmpeg   (or: choco install ffmpeg)"
    distro = _linux_distribution()
    if any(name in distro for name in ("debian", "ubuntu")):
        return "sudo apt install ffmpeg"
    if any(name in distro for name in ("fedora", "rhel", "centos")):
        return "sudo dnf install ffmpeg"
    if "arch" in distro:
        return "sudo pacman -S ffmpeg"
    if "alpine" in distro:
        return "sudo apk add ffmpeg"
    return "install ffmpeg with your package manager"


def find_ffmpeg() -> Ffmpeg:
    """Where kinemo finds ffmpeg and its version (the same lookup as the renderer)."""
    from .. import _core

    try:
        path = _core.ffmpeg_location()
    except RuntimeError as error:
        return Ffmpeg(None, None, str(error))
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=True).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return Ffmpeg(None, None, f"{path} does not run: {error}")
    first = out.splitlines()[0] if out else ""
    version = first.split(" ")[2] if first.startswith("ffmpeg version ") else first
    return Ffmpeg(path, version, None)


def require_ffmpeg() -> str:
    """The ffmpeg path, or `MissingFfmpeg` with how to install it."""
    found = find_ffmpeg()
    if found.path is None:
        raise MissingFfmpeg(
            f"video output needs ffmpeg, and it was not found ({found.problem}).\n"
            f"  install it:  {ffmpeg_install_hint()}\n"
            "  or point kinemo at it:  KINEMO_FFMPEG=/path/to/ffmpeg\n"
            "  (PNG and SVG frames and `kinemo dev` work without it)"
        )
    return found.path


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def python_version() -> str:
    return f"{platform.python_version()} ({sys.executable})"
