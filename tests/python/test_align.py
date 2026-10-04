"""Word times for audio without them: the transcription is matched to the known text, and the
syllable estimate covers what was not heard (or everything, without `kinemo[align]`)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from kinemo.audio.align import estimate_by_syllables, match, syllables, word_times


def test_syllables_of_common_words() -> None:
    assert [syllables(w) for w in ["the", "triangle", "relation", "equals", "side", "2026", "rhythm"]] == [1, 3, 3, 2, 1, 4, 1]


def test_the_estimate_follows_syllables_and_pauses() -> None:
    starts = estimate_by_syllables(["A", "relation,", "then", "more."], 4.0)
    assert starts[0] == 0.0 and starts == sorted(starts)
    # "relation," (3 syllables and a comma) takes longer than "then".
    assert starts[2] - starts[1] > starts[3] - starts[2]


def test_heard_words_are_matched_and_misheard_ones_fill_in() -> None:
    words = "every right triangle hides a relation".split()
    heard = [("every", 0.0), ("right", 0.4), ("tryangle", 0.7), ("hides", 1.2), ("a", 1.5), ("relation", 1.7)]
    times = match(words, heard, 2.5)
    assert times[0] == 0.0 and times[1] == 0.4 and times[3] == 1.2 and times[5] == 1.7
    assert 0.4 < times[2] < 1.2  # misheard: placed between its neighbours


@pytest.mark.align
@pytest.mark.skipif(os.environ.get("KINEMO_TEST_ALIGN") != "1", reason="downloads a speech model; set KINEMO_TEST_ALIGN=1")
def test_aligns_spoken_words(tmp_path: Path) -> None:
    pytest.importorskip("faster_whisper")
    say = shutil.which("say")
    if say is None:
        pytest.skip("needs macOS `say` to make speech")
    text = "Every right triangle hides a relation between its sides"
    subprocess.run([say, "-o", str(tmp_path / "line.aiff"), text], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "line.aiff"), str(tmp_path / "line.wav")], check=True)
    times, how = word_times(str(tmp_path / "line.wav"), text.split(), 4.0, str(tmp_path / "cache"), model="tiny.en")
    assert how == "aligned"
    assert times == sorted(times) and times[-1] > 1.5
