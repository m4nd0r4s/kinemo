import kinemo as k


@k.scene
def double(s: k.Scene):
    x = k.signal(0.0)
    doubled = x.map(lambda v: v * 2)
    label = k.Text(lambda: f"2 × {x():.1f} = {doubled():.1f}", size=0.8).place(at="center")
    s.add(label)
    s.play(x.to(10), duration=3)
    s.wait(0.5)
