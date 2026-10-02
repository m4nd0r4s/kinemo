import kinemo as k


@k.scene
def grid_from_center(s: k.Scene):
    squares = [k.Square(1, fill=k.TEAL, fill_opacity=0.5) for _ in range(9)]
    k.Grid(*squares, cols=3, gap=0.3).place(at="center")
    s.play(k.stagger([k.grow(q) for q in squares], lag=0.15, order="center"))
    s.wait(0.5)
