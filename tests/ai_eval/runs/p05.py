import kinemo as k


@k.scene
def title_subtitle(s: k.Scene):
    title = k.Text("Title", size=0.9).place(at="top", margin=0.8)
    subtitle = k.Text("A subtitle right below", size=0.5).place(below=title, gap=0.3)
    s.play(k.fade_in(title, subtitle))
    s.wait(0.5)
