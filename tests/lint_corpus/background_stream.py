# expect: none
"""A faint stream of digits behind the content: decoration, not text to read."""

import kinemo as k


@k.scene(background=k.rgb(0.06, 0.06, 0.06))
def stream(s: k.Scene):
    rows = [k.Text("0110100101101001", size=0.14, color=k.rgb(0.16, 0.16, 0.16), y=2.5 - 0.4 * i) for i in range(12)]
    backdrop = k.Group(*rows, emphasis="decorative")
    title = k.Text("Inside a file", size=0.7).place(at="center")
    s.add(backdrop)
    s.play(k.write(title))
    s.wait(1)
