import kinemo as k


@k.scene
def letter_by_letter(s: k.Scene):
    text = k.Text("Letter by letter", size=0.8).place(at="center")
    s.play(k.write(text), duration=2)
    s.wait(0.5)
    s.play(k.fade_out(text))
