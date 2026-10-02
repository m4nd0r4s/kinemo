import kinemo as k


@k.scene(params={"n": k.Int(3, 12, default=5), "color": k.Choice([k.BLUE, k.RED])})
def polygon(s: k.Scene, n: k.Signal[float], color: k.Signal[k.Color]):
    s.play(k.draw(k.Polygon.regular(n, color=color)))
