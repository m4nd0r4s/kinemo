import kinemo as k


@k.scene
def counter_flash(s: k.Scene):
    n = k.signal(0, lerp=k.lerp.round)
    label = k.Text(lambda: f"{n():.0f}", size=1.2).place(at="center")
    s.add(label)
    k.when(n > 5, k.flash(label, color=k.YELLOW), once=True)
    s.play(n.to(10), duration=4, ease=k.ease.linear)
    s.wait(0.5)
