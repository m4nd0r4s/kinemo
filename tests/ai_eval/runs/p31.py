import kinemo as k


@k.scene
def dashed_line(s: k.Scene):
    line = k.Line(length=14, dash=(0.3, 0.2)).place(at="center")
    dot = k.Dot(r=0.2, fill=k.RED).place(above=line, gap=1.0)
    s.play(k.draw(line))
    s.play(k.fade_in(dot))
    s.wait(0.5)
