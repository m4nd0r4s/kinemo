import kinemo as k


@k.scene
def parallel(s: k.Scene):
    a = k.Dot(r=0.25, x=-4, y=1)
    b = k.Dot(r=0.25, x=-4, y=-1, fill=k.RED)
    s.add(a, b)
    s.play(a.to(x=4, duration=1), b.to(x=4, duration=2.5))
    s.wait(1.5)
