import kinemo as k


@k.scene
def growing_arc(s: k.Scene):
    arc = k.Arc(r=2, start_angle=0, angle=0, stroke=k.ORANGE).place(at="center")
    s.add(arc)
    s.play(arc.to(angle=270), duration=2)
    s.wait(0.5)
