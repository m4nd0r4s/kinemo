import kinemo as k


@k.scene
def progress_bar(s: k.Scene):
    p = k.signal(0.0)
    track = k.Rect(w=6, h=0.5, stroke=k.GRAY, x=0, y=0)
    fill = k.Rect(w=p * 6 + 0.001, h=0.5, x=p * 3 - 3, y=0, fill=k.GREEN, fill_opacity=1, stroke=k.GREEN)
    label = k.Text(lambda: f"{p() * 100:.0f}%", size=0.6).place(above=track, gap=0.4)
    s.add(track, fill, label)
    s.play(p.to(1), duration=4, ease=k.ease.linear)
    s.wait(0.5)
