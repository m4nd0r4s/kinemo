import kinemo as k


@k.scene
def hello_world(s: k.Scene):
    title = k.Text("Hello, world", size=0.8).place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE))
    s.wait(0.5)
