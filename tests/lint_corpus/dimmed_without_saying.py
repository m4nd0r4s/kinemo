# expect: W1003
"""Text dimmed below 4.5:1 without saying it is on purpose."""

import kinemo as k


@k.scene(background=k.rgb(0.06, 0.06, 0.06))
def dimmed(s: k.Scene):
    hint = k.Text("the easy cases", size=0.5, color=k.rgb(0.4, 0.4, 0.4))
    s.add(hint)
    s.wait(1)
