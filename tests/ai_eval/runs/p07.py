import kinemo as k


@k.scene
def pythagoras(s: k.Scene):
    a = k.Math(r"a^2 + b^2 = c^2", size=0.8).place(at="center")
    b = k.Math(r"c = \sqrt{a^2 + b^2}", size=0.8).place(at="center")
    s.play(k.write(a))
    s.wait(0.5)
    s.play(k.morph(a, b), duration=1.5)
    s.wait(0.5)
