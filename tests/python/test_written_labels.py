"""Timeline labels read as the code was written; a call that runs in a loop keeps the
generated description, which tells the iterations apart."""

from __future__ import annotations

from pathlib import Path

from kinemo.cli.check import timeline_entries
from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def labels(s: k.Scene):
    txt = k.Text("one two")
    s.play(k.write(txt))
    s.play(
        txt.words[0].to(color=k.RED),
        duration=0.5,
    )
    for word in txt.words:
        s.play(k.indicate(word), duration=0.2)
'''


def test_labels_are_the_written_calls_except_in_loops(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(path)))[0], {})
    labels = [e["label"] for e in timeline_entries(result)]
    assert labels == ["k.write(txt)", "txt.words[0].to(color=k.RED)", "indicate(txt.words[0])", "indicate(txt.words[1])"]
