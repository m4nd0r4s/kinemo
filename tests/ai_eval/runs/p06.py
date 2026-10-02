import kinemo as k

VALUES = [4, 1, 3, 2]


@k.scene
def bubble_sort(s: k.Scene):
    bars = [k.Bar(v, label=True) for v in VALUES]
    row = k.Row(*bars, gap=0.3, align="bottom").place(at="center")
    s.play(k.stagger([k.grow(b, from_="bottom") for b in bars], lag=0.1))
    order = list(bars)
    vals = list(VALUES)
    n = len(vals)
    for i in range(n - 1):
        for j in range(n - 1 - i):
            a, b = order[j], order[j + 1]
            with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW), duration=0.3):
                if vals[j] > vals[j + 1]:
                    s.play(row.swap(j, j + 1), duration=0.6)
                    order[j], order[j + 1] = order[j + 1], order[j]
                    vals[j], vals[j + 1] = vals[j + 1], vals[j]
                else:
                    s.wait(0.3)
    s.wait(0.5)
