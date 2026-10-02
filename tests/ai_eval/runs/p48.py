import kinemo as k


@k.scene
def rise_change_color(s: k.Scene):
    y = k.signal(-3.0)
    color = y.map(lambda v: k.mix(k.BLUE, k.RED, (v + 3) / 6))
    dot = k.Dot(r=0.3, y=y, fill=color)
    s.add(dot)
    s.play(y.to(3), duration=3)
    s.wait(0.5)
