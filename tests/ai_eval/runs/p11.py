import kinemo as k


@k.scene
def spin_pulse(s: k.Scene):
    sq = k.Square(1.5, fill=k.BLUE, fill_opacity=0.5).place(at="center")
    s.play(k.draw(sq))
    s.play(sq.to(rotate=360, scale=1.5), duration=2)
    s.play(sq.to(scale=1, ease=k.ease.out_elastic), duration=1.5)
    s.wait(0.5)
