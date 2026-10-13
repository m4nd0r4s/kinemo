# expect: none
"""Dark text on a bright speech bubble and a bright chip."""

import kinemo as k

DARK = k.rgb(0.085, 0.095, 0.125)


@k.scene(background=k.rgb(0.055, 0.063, 0.082))
def bubble(s: k.Scene):
    host = k.Dot(r=0.12, x=-3, y=-1)
    note = k.Callout("Wait, what?", to=host, color=k.TEAL)
    chip = k.RoundedRect(w=1.4, h=0.7, radius=0.35, fill=k.YELLOW, fill_opacity=1, x=2.5, y=1)
    letter = k.Text("NEW", size=0.36, color=DARK, x=2.5, y=1)
    s.play(k.fade_in(host, note, chip, letter))
    s.wait(1)
