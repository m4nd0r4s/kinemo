import kinemo as k


@k.scene
def paragraph(s: k.Scene):
    text = k.Text(
        "This is a long text that should wrap onto several lines within a maximum width.",
        size=0.45,
        width=6,
        align="center",
    ).place(at="center")
    s.play(k.write(text), duration=2)
    s.wait(0.5)
