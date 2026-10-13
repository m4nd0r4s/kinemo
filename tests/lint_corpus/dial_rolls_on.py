# expect: none
"""A dial keeps rolling after the line that introduces it: started, not played."""

import kinemo as k


@k.scene
def dial(s: k.Scene):
    face = k.Circle(r=1.5)
    hand = k.Line(start=(0, 0), end=(0, 1.3))
    s.play(k.draw(face), k.fade_in(hand))
    with s.voice("Today's number."):  # kinemo: allow W1401 (no voice provider in tests)
        s.start(hand.to(rotate=-720), duration=3)
    s.wait(3)
