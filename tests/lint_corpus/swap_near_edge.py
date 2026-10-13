# expect: W1001
"""A swap arc near the bottom edge dips out of the frame."""

import kinemo as k


@k.scene
def swap(s: k.Scene):
    row = k.Row(*[k.Bar(v, label=True) for v in [5, 9, 3]], gap=0.2, align="bottom").place(at="bottom", margin=0.6)
    s.play(k.fade_in(row))
    s.play(row.swap(1, 2), duration=0.4)
    s.wait(0.2)
