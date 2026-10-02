import kinemo as k


@k.scene
def done(s: k.Scene):
    rate = k.signal(0.5)
    accumulated = k.integrate(rate)
    value = k.Text(lambda: f"∫ = {accumulated():.2f}").place(at="center")
    notice = k.Text("Done!", size=0.8, color=k.GREEN).place(below=value, gap=0.5)
    s.add(value)
    k.when(accumulated >= 1, k.write(notice), once=True)
    s.wait(3)
