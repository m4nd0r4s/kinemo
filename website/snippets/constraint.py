import kinemo as k


@k.scene
def constraint(s: k.Scene):
    tri = k.Triangle().place(at="center")
    title = k.Text("hypotenuse", size=0.5).place(above=tri, gap=0.3)
    s.add(tri, title)
    s.play(title.to(x=3))
