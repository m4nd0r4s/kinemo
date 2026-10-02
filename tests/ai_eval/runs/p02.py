import kinemo as k


@k.scene
def circle_square(s: k.Scene):
    circle = k.Circle(r=1.2, color=k.RED, fill_opacity=0.5).place(at="center")
    square = k.Square(2.4, color=k.GREEN, fill_opacity=0.5).place(at="center")
    s.play(k.draw(circle))
    s.play(k.morph(circle, square), duration=1.5)
    s.wait(0.5)
