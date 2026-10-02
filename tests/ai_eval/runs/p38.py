import kinemo as k


@k.scene
def table(s: k.Scene):
    data = {"name": ["Ana", "Bruno", "Carla"], "value": [12, 7, 21]}
    t = k.Table(data, size=0.45).place(at="center")
    s.play(k.fade_in(t))
    s.wait(1)
