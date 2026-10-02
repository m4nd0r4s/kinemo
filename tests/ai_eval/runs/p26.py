import kinemo as k


@k.scene
def accelerating_dots(s: k.Scene):
    dots = [k.Dot(r=0.2) for _ in range(10)]
    row = k.Row(*dots, gap=0.5).place(at="center")
    with s.tempo(1, to=5):
        for d in dots:
            s.play(k.fade_in(d), duration=0.6)
    s.wait(0.5)
