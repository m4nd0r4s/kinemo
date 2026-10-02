import kinemo as k


@k.scene(params={"sides": k.Int(3, 12, default=6)})
def polygon(s: k.Scene, sides: k.Signal[int]):
    poly = k.Polygon.regular(sides, r=2).place(at="center")
    label = k.Text(lambda: f"{sides():.0f} sides").place(below=poly, gap=0.4)
    s.play(k.draw(poly), k.fade_in(label))
    s.wait(1)
