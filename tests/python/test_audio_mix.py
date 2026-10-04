"""The audio track: clips carry their role (voice, sound, music) to the mix, `[audio] loudness`
sets the loudness target, `[audio] trim_silence` cuts the silence around narration lines, and
a scene with a voice over ducked music renders."""

from __future__ import annotations

import json
import math
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from kinemo.cli.loader import build, find_scenes, load_module
from kinemo.cli.main import main

SCENE = '''import kinemo as k


@k.scene
def episode(s: k.Scene):
    s.play(k.music("bed.wav", gain=0.3, duck=0.25, fade=0.5))
    with s.voice("line.wav"):
        s.play(k.fade_in(k.Circle()), duration=0.5)
    s.play(k.sound("bed.wav", gain=0.5))
'''


def tone(path: Path, seconds: float, silence: float = 0.0) -> None:
    rate = 8000
    quiet = b"\x00\x00" * int(rate * silence)
    sound = b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 330 * i / rate))) for i in range(int(rate * seconds)))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(quiet + sound + quiet)


def project(folder: Path, toml: str = "") -> Path:
    tone(folder / "bed.wav", 3.0)
    tone(folder / "line.wav", 1.0, silence=0.5)
    if toml:
        (folder / "kinemo.toml").write_text(toml, encoding="utf-8")
    scene = folder / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    return scene


def ir_of(scene: Path) -> dict:  # type: ignore[type-arg]
    result = build(find_scenes(load_module(str(scene)))[0], {})
    assert result.scene is not None
    return json.loads(result.scene.builder.to_json())


def test_clips_carry_their_role_and_the_scene_its_loudness(tmp_path: Path) -> None:
    ir = ir_of(project(tmp_path, "[audio]\nloudness = -16\n"))
    roles = [(clip["role"], clip["duck"], clip["fade"]) for clip in ir["audio"]]
    assert roles == [("music", 0.25, 0.5), ("voice", 0.0, 0.0), ("sound", 0.0, 0.0)]
    assert ir["config"]["loudness"] == -16.0


def test_trim_silence_cuts_the_silence_around_a_line(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    (tmp_path / "trimmed").mkdir()
    plain = ir_of(project(tmp_path / "plain"))
    trimmed = ir_of(project(tmp_path / "trimmed", "[audio]\ntrim_silence = true\n"))
    voice_plain = next(c for c in plain["audio"] if c["role"] == "voice")
    voice_trimmed = next(c for c in trimmed["audio"] if c["role"] == "voice")
    assert voice_trimmed["path"] != voice_plain["path"]
    # 0.5 s of silence on each side of a 1 s tone: about 1.1 s are left (margins included).
    sound_plain = next(c for c in plain["audio"] if c["role"] == "sound")["t"]
    sound_trimmed = next(c for c in trimmed["audio"] if c["role"] == "sound")["t"]
    assert sound_plain == pytest.approx(2.0)
    assert sound_trimmed == pytest.approx(1.1, abs=0.02)


def test_a_voice_over_ducked_music_renders(tmp_path: Path) -> None:
    scene = project(tmp_path, "[audio]\nloudness = -16\n")
    out = tmp_path / "episode.mp4"
    assert main(["render", str(scene), "--quality", "draft", "--progress", "none", "--out", str(out)]) == 0
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert "audio" in probe.stdout
