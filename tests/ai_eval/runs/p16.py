import kinemo as k


@k.scene
def digital_clock(s: k.Scene):
    seconds = k.time.map(lambda t: k.min(k.floor(t), 10))
    clock = k.Text(lambda: f"00:{seconds():02.0f}", size=1.2).place(at="center")
    s.add(clock)
    s.wait(11)
