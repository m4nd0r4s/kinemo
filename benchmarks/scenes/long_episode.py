"""A long, episode-like scene (~10 minutes): sections that build, animate and clear."""

import kinemo as k


@k.scene
def long_episode(s: k.Scene):
    for section in range(60):
        title = k.Text(f"Section {section}", size=0.6).place(at="top", gap=0.5)
        boxes = [k.Square(0.8, fill=k.BLUE, fill_opacity=0.5) for _ in range(6)]
        row = k.Row(*boxes, gap=0.3).place(at="center")
        label = k.Text("each box is a step of the algorithm", size=0.3).place(below=row, gap=0.4)
        ax = k.Axes(x=(0, 10, 2), y=(0, 5, 1), width=5, height=2.5).place(at="bottom", gap=0.4)
        curve = ax.plot(lambda x: 0.05 * x * x)
        s.play(k.write(title), k.fade_in(row))
        s.play(k.write(label), k.draw(ax))
        s.wait(2)
        s.play(row.swap(0, 5), duration=1)
        s.play(ax.zoom_to(x=(0, 5)), duration=1.5)
        s.wait(2)
        s.play(k.fade_out(title, row, label, ax, curve))
