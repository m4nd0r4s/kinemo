import kinemo as k


@k.scene
def arrow_follows(s: k.Scene):
    sq = k.Square(1.5, x=-4, y=0)
    circ = k.Circle(r=0.8, x=4, y=0)
    arrow = k.Arrow(
        start=k.vec(sq.x + 0.85, sq.y),
        end=k.vec(circ.x - 0.9, circ.y),
        stroke=k.YELLOW,
        fill=k.YELLOW,
    )
    s.play(k.draw(sq), k.draw(circ))
    s.play(k.draw(arrow))
    s.play(circ.to(x=2, y=2.5), duration=2)
    s.wait(0.5)
