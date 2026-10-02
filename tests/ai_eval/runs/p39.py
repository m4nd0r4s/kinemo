import kinemo as k


@k.scene
def bars(s: k.Scene):
    before = {"cat": ["A", "B", "C", "D"], "value": [3, 5, 2, 4]}
    after = {"cat": ["A", "B", "C", "D"], "value": [6, 2, 4, 5]}
    chart = k.BarChart(before, x="cat", y="value", key="cat").place(at="center")
    s.play(k.draw(chart))
    s.wait(0.5)
    s.play(chart.to(data=after), duration=2)
    s.wait(0.5)
