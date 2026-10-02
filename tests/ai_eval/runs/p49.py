import kinemo as k


@k.scene
def years(s: k.Scene):
    months = [1, 2, 3, 4, 5, 6]
    # the y= columns must exist in both datasets: relative years
    d1 = {"month": months, "previous year": [3, 4, 5, 4, 6, 7], "current year": [4, 5, 5, 6, 7, 8]}
    d2 = {"month": months, "previous year": [4, 5, 5, 6, 7, 8], "current year": [5, 6, 7, 7, 9, 10]}
    chart = k.LineChart(d1, x="month", y=["previous year", "current year"], y_range=(0, 12), dots=True).place(at="center")
    year = k.Text("2022 → 2023", size=0.5).place(at="top", margin=0.6)
    s.play(k.draw(chart), k.write(year), duration=2)
    s.wait(0.5)
    s.play(chart.to(data=d2), year.to(text="2023 → 2024"), duration=2)
    s.wait(0.5)
