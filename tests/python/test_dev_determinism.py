"""`kinemo dev` checks that two builds of the same source agree, off the rebuild path: in the
background, after a quiet moment, and only for the latest build."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from kinemo.cli import dev_session
from kinemo.cli.dev import Session
from test_dev_editing import FakeServer

IMPURE = '''import itertools
import kinemo as k

COUNTER = itertools.count()


@k.scene
def demo(s: k.Scene):
    s.add(k.Dot(r=0.2, x=next(COUNTER)))
    s.wait(0.5)
'''


def wait_for_checks() -> None:
    deadline = time.monotonic() + 10
    while any(t.name == "kinemo-determinism" for t in threading.enumerate()) and time.monotonic() < deadline:
        time.sleep(0.01)


def session_for(tmp_path: Path) -> Session:
    path = tmp_path / "scene.py"
    path.write_text(IMPURE, encoding="utf-8")
    return Session(str(path), None, {}, FakeServer())  # type: ignore[arg-type]


def test_rebuild_does_not_wait_for_the_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(dev_session, "DETERMINISM_IDLE_SECONDS", 0.3)
    session = session_for(tmp_path)
    start = time.monotonic()
    assert session.rebuild()
    assert time.monotonic() - start < 0.3
    assert "different results" not in capsys.readouterr().out
    wait_for_checks()
    assert "different results" in capsys.readouterr().out


def test_a_newer_build_drops_the_pending_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(dev_session, "DETERMINISM_IDLE_SECONDS", 0.2)
    session = session_for(tmp_path)
    assert session.rebuild()
    session.generation += 1  # a newer build started before the check ran
    wait_for_checks()
    assert "different results" not in capsys.readouterr().out
