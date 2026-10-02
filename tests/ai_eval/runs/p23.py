import kinemo as k


@k.scene
def swap_positions(s: k.Scene):
    a = k.Text("one", size=0.7)
    b = k.Text("two", size=0.7)
    c = k.Text("three", size=0.7)
    row = k.Row(a, b, c, gap=0.8).place(at="center")
    s.play(k.write(row))
    s.play(row.to(children=[b, c, a]), duration=1.2)
    s.wait(0.5)
