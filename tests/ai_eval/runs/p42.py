import kinemo as k


@k.scene
def growing_square(s: k.Scene):
    sq = k.Square(2, fill=k.GREEN, fill_opacity=0.5).place(at="center")
    s.play(k.grow(sq, from_="bottom"))
    s.wait(0.5)
