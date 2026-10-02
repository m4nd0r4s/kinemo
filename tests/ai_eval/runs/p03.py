import kinemo as k


@k.scene
def three_circles(s: k.Scene):
    circles = [k.Circle(r=0.8) for _ in range(3)]
    k.Row(*circles, gap=0.8).place(at="center")
    for c in circles:
        s.play(k.fade_in(c), duration=0.6)
    s.wait(0.5)
