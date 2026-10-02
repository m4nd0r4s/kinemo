import kinemo as k


@k.scene
def pythagoras(s: k.Scene):
    a, b, c = 1.5, 2.0, 2.5
    tri = k.Polygon((0, 0), (b, 0), (0, a)).place(at="center")
    s.play(k.draw(tri))
    q_a = k.Square(a, fill=k.BLUE, fill_opacity=0.4).place(left_of=tri, gap=0.0)
    q_b = k.Square(b, fill=k.GREEN, fill_opacity=0.4).place(below=tri, gap=0.0)
    q_c = k.Square(c, fill=k.RED, fill_opacity=0.4, rotate=36.87).place(right_of=tri, gap=0.2)
    s.play(k.stagger([k.draw(q_a), k.draw(q_b), k.draw(q_c)], lag=0.3))
    s.play(k.indicate(q_c, color=k.YELLOW, scale=1.1))
    s.wait(0.5)
