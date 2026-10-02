import kinemo as k


@k.scene
def circle_trail(s: k.Scene):
    angle = k.time * 2
    dot = k.Dot(r=0.15, fill=k.YELLOW, x=k.cos(angle) * 2.5, y=k.sin(angle) * 2.5)
    trail = k.trace(dot.world.position, length=1.5, stroke=k.TEAL)
    s.add(trail, dot)
    s.wait(5)
