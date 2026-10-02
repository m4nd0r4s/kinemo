import kinemo as k


@k.scene
def moving_dot(s: k.Scene):
    dot = k.Dot(r=0.2, x=-6)
    s.add(dot)
    s.play(dot.to(x=6), duration=3, ease=k.ease.linear)
    s.wait(0.5)
