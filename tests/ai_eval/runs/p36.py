import kinemo as k


@k.scene
def axis_zoom(s: k.Scene):
    ax = k.Axes(x=(0, 10, 1), y=(0, 10, 2)).place(at="center")
    ax.plot(lambda x: x, color=k.YELLOW)
    s.play(k.draw(ax))
    s.play(ax.zoom_to(x=(2, 4)), duration=1.5)
    s.wait(0.5)
