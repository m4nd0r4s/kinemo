# expect: none
"""Digits flip and a number folds into a formula: crossfades between texts."""

import kinemo as k


@k.scene
def digits(s: k.Scene):
    zero = k.Text("0", size=0.8).place(at="center")
    one = k.Text("1", size=0.8).place(at="center")
    number = k.Text("1089", size=0.6).place(at="bottom", margin=1.5)
    formula = k.Math(r"x^2 + 1").place(at="bottom", margin=1.5)
    s.play(k.fade_in(zero, number))
    s.play(k.morph(zero, one), k.morph(number, formula))
    s.wait(1)
