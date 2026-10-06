"""Series cards: parts, theme colors and the entrance of `k.draw(card)`."""

from __future__ import annotations

import kinemo as k
from conftest import build


def test_title_card_parts_and_entrance() -> None:
    seen: dict[str, object] = {}
    took: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        card = k.TitleCard("Adding", kicker="EPISODE 2", subtitle="How computers do math")
        start = s.mark()
        s.play(k.draw(card))
        seen["parts"] = [card.kicker is not None, card.title.text.now, card.subtitle is not None]
        took.append(s.mark() - start)
        seen["rule_width"] = abs(float(card.rule.end.now[0] - card.rule.start.now[0]))  # type: ignore[index]
        seen["title_width"] = float(card.title.width.now)

    assert seen["parts"] == [True, "Adding", True]
    assert took[0] > 0
    assert abs(seen["rule_width"] - seen["title_width"]) < 1e-6  # type: ignore[operator]


def test_end_card_and_lower_third_build_with_optional_parts() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        end = k.EndCard()
        who = k.LowerThird("Ada", side="right")
        s.play(k.draw(end), k.draw(who))
        seen["end"] = (end.next, end.brand)
        seen["right"] = float(who.title.x.now) < 0

    assert seen["end"] == (None, None)
    assert seen["right"] is True
