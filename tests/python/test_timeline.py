"""Cursor semantics: play/start/wait, duration rescaling, at=, tempo, during, marks."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import animations, build, ir, line_of, lint_codes, prop_timeline, raises_code


def test_play_advances_cursor_and_returns_timespan() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        seen.append(s.play(c.to(x=2)))
        seen.append(s.cursor)

    span, cursor = seen
    assert (span.start, span.end, span.duration) == (0.0, 1.0, 1.0)
    assert cursor == 1.0
    assert animations(scene, "c", "x") == [(0.0, 1.0)]


def test_start_does_not_advance_cursor_but_extends_scene() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        seen.append(s.start(c.to(x=2, duration=3)))
        seen.append(s.cursor)

    span, cursor = seen
    assert (span.start, span.end) == (0.0, 3.0)
    assert cursor == 0.0
    assert scene.duration == pytest.approx(3.0 + 0.5)


def test_wait_advances_cursor_default_one_second() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        seen.append(s.wait())
        seen.append(s.wait(0.25))
        seen.append(s.cursor)

    first, second, cursor = seen
    assert (first.start, first.end) == (0.0, 1.0)
    assert (second.start, second.end) == (1.0, 1.25)
    assert cursor == 1.25


def test_scene_duration_is_cursor_plus_tail() -> None:
    def body(s: k.Scene) -> None:
        s.wait(2)

    assert build(body).duration == pytest.approx(2.5)
    assert build(body, tail=0).duration == pytest.approx(2.0)


def test_play_several_animations_runs_them_in_parallel() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.add(a, b)
        s.play(a.to(x=1), b.to(x=1, duration=2))

    assert animations(scene, "a", "x") == [(0.0, 1.0)]
    assert animations(scene, "b", "x") == [(0.0, 2.0)]


def test_duration_rescales_parallel_to_total() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.add(a, b)
        s.play(a.to(x=1), b.to(x=1), duration=2)

    assert animations(scene, "a", "x") == [(0.0, 2.0)]
    assert animations(scene, "b", "x") == [(0.0, 2.0)]


def test_duration_rescales_parallel_proportionally() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.add(a, b)
        s.play(k.par(a.to(x=1), b.to(x=1, duration=4)), duration=2)

    assert animations(scene, "a", "x") == [(0.0, 0.5)]
    assert animations(scene, "b", "x") == [(0.0, 2.0)]


def test_duration_rescales_seq_children_proportionally() -> None:
    @build
    def equal(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.seq(c.to(x=1), c.to(x=2)), duration=2)

    assert animations(equal, "c", "x") == [(0.0, 1.0), (1.0, 2.0)]

    @build
    def unequal(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.seq(c.to(x=1), c.to(x=2, duration=3)), duration=2)

    assert animations(unequal, "c", "x") == [(0.0, 0.5), (0.5, 2.0)]


def test_stagger_offsets_each_child_by_lag() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.add(a, b)
        s.play(k.stagger([a.to(x=1), b.to(x=1)], lag=0.25))

    assert animations(scene, "a", "x") == [(0.0, 1.0)]
    assert animations(scene, "b", "x") == [(0.25, 1.25)]


def test_at_schedules_absolutely_without_moving_cursor_and_lints_w0110() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        seen.append(s.play(c.to(x=1), at=2))  # W0110-here
        seen.append(s.cursor)

    span, cursor = seen
    assert (span.start, span.end) == (2.0, 3.0)
    assert cursor == 0.0
    assert lint_codes(scene) == ["W0110"]
    lint = scene.lints.items[0]
    assert lint.level == "warning"
    assert lint.spans[0].file == __file__
    assert lint.spans[0].line == line_of("# W0110-here")
    assert any("s.start" in (fix.code or "") for fix in lint.fixes)


def test_start_with_at_does_not_lint() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1), at=2)

    assert lint_codes(scene) == []
    assert animations(scene, "c", "x") == [(2.0, 3.0)]


def test_constant_tempo_divides_durations_and_waits() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.tempo(2):
            seen.append(s.play(c.to(x=1)))
            seen.append(s.wait(1))
        seen.append(s.play(c.to(x=0)))

    played, waited, after = seen
    assert (played.start, played.end) == (0.0, 0.5)
    assert (waited.start, waited.end) == (0.5, 1.0)
    assert (after.start, after.end) == (1.0, 2.0)


def test_nested_tempos_multiply() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.tempo(2), s.tempo(2):
            seen.append(s.play(c.to(x=1)))

    assert seen[0].duration == pytest.approx(0.25)


def test_progressive_tempo_makes_block_shorter() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.tempo(1, to=4):
            s.play(c.to(x=1))
            s.wait(1)
        seen.append(s.cursor)

    (cursor,) = seen
    # Unwarped the block lasts 2 s; at 1× → 4× it must be shorter than 2 s and
    # longer than the 0.5 s it would take at a constant 4×.
    assert 0.5 < cursor < 2.0
    ((t0, t1),) = animations(scene, "c", "x")
    assert t0 == pytest.approx(0.0)
    # The first half runs slower than the second half, so it keeps more than half the time.
    assert cursor / 2 < t1 < cursor


def test_progressive_tempo_warps_marks_inside_the_block() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        with s.tempo(1, to=4):
            s.wait(1)
            s.mark("mid")
            s.wait(1)
        seen.append(s.cursor)

    (end,) = seen
    assert end / 2 < scene.marks["mid"] < end


def test_invalid_tempo_is_an_error() -> None:
    def body(s: k.Scene) -> None:
        with s.tempo(0):
            pass

    with raises_code("K0105"):
        build(body)


def test_during_applies_on_entry_and_reverts_on_exit() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.during(c.to(x=3)):
            seen.append(("inside", s.cursor, c.x.now))
            s.wait(1)
        seen.append(("after", s.cursor, c.x.now))

    assert seen == [("inside", 1.0, 3.0), ("after", 3.0, 0.0)]
    # The revert reuses the duration of the entry.
    assert animations(scene, "c", "x") == [(0.0, 1.0), (2.0, 3.0)]


def test_during_duration_applies_to_entry_and_revert() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.during(c.to(x=3), duration=0.2):
            s.wait(1)

    assert animations(scene, "c", "x") == [(0.0, 0.2), (1.2, pytest.approx(1.4))]


def test_during_revert_instant_sets_back_at_exit() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        with s.during(c.to(x=3), revert="instant"):
            s.wait(1)
        seen.append((s.cursor, c.x.now))

    assert seen == [(2.0, 0.0)]
    timeline = prop_timeline(scene, "c", "x")
    assert [e["k"] for e in timeline] == ["anim", "set"]
    assert timeline[1]["t"] == 2.0


def test_during_allows_decisions_on_now_inside_the_block() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        value = k.signal(3.0)
        c = k.Circle()
        s.add(c)
        with s.during(c.to(color=k.YELLOW), duration=0.2):
            if value.now > 2:
                s.play(c.to(x=1))
            seen.append(c.x.now)

    assert seen == [1.0]


def test_marks_record_cursor_names_and_slides() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        seen.append(s.mark("start"))
        s.wait(1.5)
        seen.append(s.mark("chorus", slide=True))
        s.mark()
        seen.append(s.cursor)

    assert seen == [0.0, 1.5, 1.5]
    assert scene.marks == {"start": 0.0, "chorus": 1.5}
    assert ir(scene)["marks"] == [
        {"name": "start", "t": 0.0, "slide": False},
        {"name": "chorus", "t": 1.5, "slide": True},
        {"name": None, "t": 1.5, "slide": False},
    ]


def test_marks_can_anchor_later_animations() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.wait(1)
        s.mark("x")
        s.wait(2)
        s.start(c.to(x=1), at=s.marks["x"] + 0.5)

    assert animations(scene, "c", "x") == [(1.5, 2.5)]


def test_animation_with_returns_rescaled_copy() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        base = c.to(x=1)
        s.play(base.with_(duration=2, delay=0.5))

    assert animations(scene, "c", "x") == [(0.5, 2.5)]


def test_empty_play_is_k0203() -> None:
    with raises_code("K0203"):
        build(lambda s: s.play())


def test_play_of_non_animation_is_k0203() -> None:
    with raises_code("K0203"):
        build(lambda s: s.play(42))  # type: ignore[arg-type]


def test_negative_wait_is_k0202() -> None:
    with raises_code("K0202"):
        build(lambda s: s.wait(-1))
