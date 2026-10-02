import kinemo as k


@k.scene
def item_list(s: k.Scene):
    items = [k.Text(t, size=0.5) for t in ("• first item", "• second item", "• third item")]
    k.Column(*items, gap=0.4, align="left").place(at="center")
    for item in items:
        s.play(k.fade_in(item), duration=0.7)
    s.wait(0.5)
