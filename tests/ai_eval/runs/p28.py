import kinemo as k


@k.scene
def slides(s: k.Scene):
    title = k.Text("Title", size=0.9).place(at="center")
    s.play(k.write(title))
    s.wait(1)
    s.play(k.fade_out(title))

    s.mark("development", slide=True)
    body = k.Text("Development", size=0.7).place(at="top", margin=0.8)
    c = k.Circle(r=1.2).place(at="center")
    s.play(k.write(body), k.draw(c))
    s.wait(1)
    s.play(k.fade_out(body, c))

    s.mark("conclusion", slide=True)
    end = k.Text("Conclusion", size=0.9).place(at="center")
    s.play(k.write(end))
    s.wait(1)
