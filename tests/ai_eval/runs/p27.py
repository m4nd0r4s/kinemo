import kinemo as k


def temp_color(t):
    return k.mix(k.BLUE, k.RED, k.clamp(t / 100, 0, 1))


class Thermometer(k.Component):
    temperature: k.Prop[float] = k.prop(20.0, range=(0, 100))

    def build(self) -> k.Node:
        self.tube = k.RoundedRect(w=0.8, h=4.2, radius=0.4)
        self.bar = k.Rect(
            w=0.5,
            h=self.temperature.map(lambda t: 0.05 + t * 0.04),
            fill=self.temperature.map(temp_color),
            fill_opacity=1,
        ).place(inside=self.tube, align="bottom", pad=0.1)
        return k.Group(self.tube, self.bar)


@k.scene
def thermometer(s: k.Scene):
    t = Thermometer(temperature=10).place(at="center")
    label = k.Text(lambda: f"{t.temperature():.0f} °C").place(right_of=t, gap=0.5)
    s.play(k.draw(t), k.fade_in(label))
    s.play(t.to(temperature=90), duration=2)
    s.play(t.to(temperature=40), duration=1.5)
    s.wait(0.5)
