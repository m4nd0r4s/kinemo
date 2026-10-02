import kinemo as k


@k.scene
def group_to_corner(s: k.Scene):
    circle = k.Circle(r=1.2, fill=k.BLUE, fill_opacity=0.3)
    text = k.Text("A", size=0.8).place(inside=circle)
    group = k.Group(circle, text).place(at="center")
    s.play(k.draw(group))
    s.play(group.to(place=dict(at="top-left", margin=0.8)), duration=1.5)
    s.wait(0.5)
