# expect: W1002
"""A label placed by hand lands on the title."""

import kinemo as k


@k.scene
def overlap(s: k.Scene):
    title = k.Text("A thrown ball", size=0.6).place(at="top", margin=0.6)
    speed = k.Text("v0 = 3 m/s", size=0.4, x=1.2, y=3.3)
    s.play(k.write(title))
    s.play(k.fade_in(speed))
    s.wait(1)
