# expect: none
"""A byte as lit and off cells: off digits are dimmed on purpose."""

import kinemo as k

INK = k.WHITE
PANEL = k.rgb(0.085, 0.095, 0.125)


@k.scene(background=k.rgb(0.055, 0.063, 0.082))
def register(s: k.Scene):
    cells: list[k.Node] = []
    for i, bit in enumerate("10110010"):
        on = bit == "1"
        x = -2.8 + 0.8 * i
        cells.append(k.RoundedRect(w=0.6, h=0.6, radius=0.08, fill=INK if on else PANEL, fill_opacity=1, x=x))
        cells.append(k.Text(bit, size=0.32, color=PANEL if on else k.GRAY, x=x, emphasis="normal" if on else "low"))
    s.play(k.fade_in(*cells))
    s.wait(1)
