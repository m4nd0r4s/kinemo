import kinemo as k


@k.scene
def scene_a(s: k.Scene):
    c = k.Circle(r=1.5, fill=k.BLUE, fill_opacity=0.4).place(at="center")
    s.play(k.draw(c))
    s.wait(1)


@k.scene
def scene_b(s: k.Scene):
    t = k.Text("Second scene", size=0.8).place(at="center")
    s.play(k.write(t))
    s.wait(1)


movie = k.movie([scene_a, scene_b], transitions=[k.crossfade(0.5)])
