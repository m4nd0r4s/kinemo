import kinemo as k


@k.scene
def equations(s: k.Scene):
    eq1 = k.Math(r"2y + 3 = 7")
    eq2 = k.Math(r"3\id{x}{x} - 1 = 5")
    col = k.Column(eq1, eq2, gap=0.6).place(at="center")
    s.play(k.write(col))
    s.play(eq2["x"].to(color=k.YELLOW))
    s.wait(0.5)
