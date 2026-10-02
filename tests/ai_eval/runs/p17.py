import kinemo as k


@k.scene
def important_word(s: k.Scene):
    before = k.Text("This is very", size=0.7)
    word = k.Text("important", size=0.7)
    k.Row(before, word, gap=0.2, align="bottom").place(at="center")
    s.play(k.write(before), k.write(word))
    s.play(word.to(color=k.YELLOW))
    s.wait(0.5)
