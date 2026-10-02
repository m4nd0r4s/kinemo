"""`@k.clip` keeps the parameters after `s`: wrong arguments are static errors."""


import kinemo as k


@k.clip
def present(s: k.Scene, obj: k.Node, pause: float = 0.3) -> None:
    s.play(k.draw(obj))
    s.wait(pause)


class Tank(k.Component):
    level: k.Prop[float] = k.prop(0.0)

    def build(self) -> k.Node:
        return k.Rect(1, 2)

    @k.clip
    def fill_up(self, s: k.Scene, to: float = 1.0) -> None:
        s.play(self.to(level=to))


@k.scene
def clips(s: k.Scene) -> None:
    dot = k.Dot()
    tank = Tank()
    animation: k.Animation = present(dot)
    s.play(animation)
    s.play(present(dot, pause=0.5))
    s.play(tank.fill_up(to=0.5))
    present(1)  # pyright: ignore[reportArgumentType]
    present(dot, "slow")  # pyright: ignore[reportArgumentType]
    present()  # pyright: ignore[reportCallIssue]
    tank.fill_up(to="full")  # pyright: ignore[reportArgumentType]
