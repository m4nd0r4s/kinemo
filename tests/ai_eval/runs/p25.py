import kinemo as k


@k.scene
def highlight_explanation(s: k.Scene):
    box = k.Rect(w=4, h=2, color=k.BLUE, fill_opacity=0.3).place(at="center")
    note = k.Text("This rectangle is the area of interest", size=0.45).place(below=box, gap=0.4)
    s.play(k.draw(box))
    with s.during(box.to(color=k.YELLOW), duration=0.4):
        s.play(k.write(note))
        s.wait(1.5)
    s.wait(0.5)
