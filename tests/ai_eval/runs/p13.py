import kinemo as k

V1 = """
def total(xs):
    t = 0
    for x in xs:
        t += x
    return t
"""

V2 = """
def total(xs):
    return sum(xs)
"""


@k.scene
def loop_to_sum(s: k.Scene):
    a = k.Code(V1, lang="python").place(at="center")
    b = k.Code(V2, lang="python").place(at="center")
    s.play(k.write(a))
    s.wait(0.5)
    s.play(k.morph(a, b), duration=1.5)
    s.wait(0.5)
