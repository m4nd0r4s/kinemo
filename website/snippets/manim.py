import kinemo as k


@k.scene
def manim_habits(s: k.Scene):
    circle = k.Circle(r=1)
    s.play(Create(circle))
