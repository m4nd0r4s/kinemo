"""A style written once and unpacked into several objects stays checked."""

import kinemo as k

dashed: k.PaintKeywords = {"stroke": k.GRAY, "dash": (8, 8)}
warm: k.ColorKeywords = {"color": k.ORANGE}
caption: k.TextKeywords = {"color": k.YELLOW, "mono": True, "opacity": 0.8}
card: k.RectKeywords = {"radius": 0.2, "fill": k.BLUE, "fill_opacity": 0.3}


@k.scene
def reused(s: k.Scene) -> None:
    line = k.Line(start=(-2, 0), end=(2, 0), **dashed)
    ring = k.Circle(r=1, **dashed, **warm)
    label = k.Text("styled", **caption)
    box = k.RoundedRect(w=3, h=2, **card)
    arrow = k.Arrow(start=(0, -1), end=(0, 1), **dashed)
    s.add(line, ring, label, box, arrow)
