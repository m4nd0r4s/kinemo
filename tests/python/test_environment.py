"""First run: a missing ffmpeg is a clear message with an install hint, and `kinemo doctor`."""

from __future__ import annotations

from pathlib import Path

import pytest

from kinemo.cli import environment
from kinemo.cli.main import main


@pytest.mark.parametrize(("system", "distro", "expected"), [("Darwin", "", "brew install ffmpeg"), ("Windows", "", "winget install"), ("Linux", "ubuntu debian", "sudo apt install ffmpeg"), ("Linux", "fedora", "sudo dnf install ffmpeg")])
def test_install_hint_follows_the_system(monkeypatch: pytest.MonkeyPatch, system: str, distro: str, expected: str) -> None:
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr(environment, "_linux_distribution", lambda: distro)
    assert expected in environment.ffmpeg_install_hint()


def test_render_without_ffmpeg_is_a_message_not_a_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text("import kinemo as k\n\n@k.scene\ndef intro(s: k.Scene):\n    s.wait(0.5)\n", encoding="utf-8")
    monkeypatch.setenv("KINEMO_FFMPEG", str(tmp_path / "missing"))
    assert main(["render", str(scene), "--out", str(tmp_path / "out")]) == 2
    out = capsys.readouterr().out
    assert "needs ffmpeg" in out and "install it:" in out and "Traceback" not in out


def test_doctor_reports_the_setup(capsys: pytest.CaptureFixture[str]) -> None:
    status = main(["doctor"])
    out = capsys.readouterr().out
    assert out.startswith("kinemo ") and "ffmpeg" in out and "python" in out
    assert status in (0, 1)
