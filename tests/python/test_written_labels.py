"""Timeline labels read as the code was written; a call that runs in a loop keeps the
generated description, which tells the iterations apart."""

from __future__ import annotations

from pathlib import Path

from kinemo.cli.check import timeline_entries
from kinemo.cli.loader import build, find_scenes, load_module
from kinemo.scene.written_labels import written_labels

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


def test_audio_verbs_in_a_loop_are_labelled_by_their_file(tmp_path: Path) -> None:
    import wave

    with wave.open(str(tmp_path / "click.wav"), "wb") as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * 800)
    scene = tmp_path / "scene.py"
    scene.write_text(
        "import kinemo as k\n\n\n@k.scene\ndef clicks(s: k.Scene):\n"
        "    s.start(k.music('click.wav'))\n"
        "    for i in range(2):\n"
        "        s.play(k.sound('click.wav'), k.fade_in(k.Dot(x=i)), duration=0.3)\n",
        encoding="utf-8",
    )
    result = build(find_scenes(load_module(str(scene)))[0], {})
    assert result.scene is not None
    labels = [label for label in written_labels(sorted(result.scene._log, key=lambda e: (e.start, e.end)))]
    assert labels[0] == "k.music('click.wav')"
    assert all(label.startswith("sound(click.wav), ") for label in labels[1:]), labels
