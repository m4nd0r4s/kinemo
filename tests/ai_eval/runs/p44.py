import kinemo as k


@k.scene
def follow_square(s: k.Scene):
    track = k.Square(4, stroke=k.GRAY).place(at="center")
    ball = k.Circle(r=0.3, fill=k.BLUE, fill_opacity=1)
    mark = k.Line(start=(0, 0), end=(0.3, 0), stroke=k.WHITE)
    wheel = k.Group(ball, mark)
    s.add(track, wheel)
    s.play(k.follow(wheel, track, rotate=True), duration=4, ease=k.ease.linear)
