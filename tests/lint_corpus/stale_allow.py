# expect: W0120
"""An allow left behind after the problem went away."""

import kinemo as k


@k.scene
def stale(s: k.Scene):
    title = k.Text("Fine now", size=0.6).place(at="center")  # kinemo: allow W1002
    s.play(k.write(title))
    s.wait(1)
