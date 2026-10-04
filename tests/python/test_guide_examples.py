"""Every complete example of the guide (a `python` block with `import kinemo` and a
`@k.scene`) passes `kinemo check --strict`, and every `python` block is valid Python (API
signatures are fenced `python signature`). Blocks that read media files get small stand-ins
next to them (a PNG, an SVG with the ids the guide uses, a WAV, a
narration script)."""

from __future__ import annotations

import ast
import re
import struct
import wave
import zlib
from pathlib import Path

import pytest

from kinemo.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
BLOCK = re.compile(r"^```python\n(.*?)^```", re.S | re.M)

MACHINE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120">
<rect id="motor" x="10" y="10" width="80" height="100" fill="#4C9BE8"/>
<circle id="shaft" cx="50" cy="60" r="20" fill="#F2F2F2"/>
<path id="belt" d="M50 40 L150 40 M50 80 L150 80" stroke="#CCCCCC" stroke-width="4" fill="none"/>
</svg>"""

SCRIPT = """### B01 · The claim

> Every right [triangle]{tri} hides a relation between its sides.

### B02 · The relation

> The square on the long side equals the two other squares.
"""


def _examples() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for chapter in sorted((ROOT / "docs" / "guide").glob("*.md")):
        for index, match in enumerate(BLOCK.finditer(chapter.read_text(encoding="utf-8")), 1):
            code = match.group(1)
            if "import kinemo" in code and "@k.scene" in code:
                found.append((f"{chapter.stem}#{index}", code))
    return found


def _png(path: Path) -> None:
    width, height = 4, 3
    rows = b"".join(b"\x00" + bytes([200, 120, 60]) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * 8000)


EXAMPLES = _examples()


@pytest.mark.parametrize(("name", "code"), EXAMPLES, ids=[name for name, _ in EXAMPLES])
def test_guide_example_passes_strict_check(name: str, code: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for module in ("polars", "pyarrow", "pandas", "numpy"):
        if re.search(rf"^import {module}|^from {module}", code, re.M):
            pytest.importorskip(module)
    _png(tmp_path / "photo.png")
    (tmp_path / "machine.svg").write_text(MACHINE_SVG, encoding="utf-8")
    _wav(tmp_path / "narration.wav")
    (tmp_path / "script.md").write_text(SCRIPT, encoding="utf-8")
    scene = tmp_path / "example.py"
    scene.write_text(code, encoding="utf-8")
    status = main(["check", "--strict", str(scene)])
    assert status == 0, f"{name}:\n{capsys.readouterr().out}"


def test_the_guide_has_examples() -> None:
    assert len(EXAMPLES) > 90


def test_python_blocks_of_the_guide_are_python() -> None:
    """API signatures (`k.Text(text="", *, size=None, ...)`) are fenced `python signature`."""
    for chapter in sorted((ROOT / "docs" / "guide").glob("*.md")):
        for index, match in enumerate(BLOCK.finditer(chapter.read_text(encoding="utf-8")), 1):
            try:
                ast.parse(match.group(1))
            except SyntaxError as error:
                raise AssertionError(f"{chapter.name} block {index}: {error}; fence signatures as `python signature`") from error
