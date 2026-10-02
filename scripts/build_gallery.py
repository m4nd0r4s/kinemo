"""Build docs/examples/: one page per repository example with rendered frames and code.

Run from the repository root: `.venv/bin/python scripts/build_gallery.py`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
OUT = ROOT / "docs" / "examples"
IMAGES = OUT / "images"

#: name → (title, what it shows, features with reference anchors, frame fractions)
GALLERY: dict[str, tuple[str, str, list[str], tuple[float, ...]]] = {
    "hello": ("Hello", "The smallest scene: write a title, then animate its color and scale.",
              ["k.Text", "k.write", "Node.to"], (0.15, 0.7)),
    "bubble_sort": ("Bubble sort", "Ordinary Python logic in the build phase drives a sorting animation: bars reflow when swapped, comparisons are highlighted with `s.during`, and `s.tempo` accelerates the run.",
                    ["k.Bar", "k.Row", "Group.swap", "Scene.during", "Scene.tempo", "k.stagger"], (0.05, 0.3, 0.98)),
    "derivative": ("Derivative", "A tangent slides along a curve while a reactive label shows the slope; the axes zoom at the end.",
                   ["k.Axes", "Axes.plot", "Plot.tangent_at", "Plot.point_at", "Axes.zoom_to", "k.signal"], (0.3, 0.6, 0.98)),
    "pythagoras": ("Pythagoras", "Squares built on the sides of a right triangle, a clip, a highlight with `s.during` and a structural morph between two equations.",
                   ["k.Triangle", "Square.on", "k.clip", "k.Math", "k.morph"], (0.2, 0.55, 0.83, 0.98)),
    "solar_day": ("A day with solar + battery", "A component integrates power into a state of charge, fires `full`/`empty` events with hysteresis, and reads its clock from a context; the load curve comes from a polars DataFrame.",
                  ["k.Component", "k.integrate", "k.when", "k.context", "k.interp"], (0.25, 0.55, 0.85)),
    "bounce": ("Bouncing ball", "A fixed-step simulation with typed events; each impact squashes the ball and the script waits for the third bounce.",
               ["k.simulate", "k.State", "Scene.wait_for", "k.squash"], (0.07, 0.19, 0.4)),
    "polygon": ("Parametric polygon", "A scene parameter drives the number of sides (`kinemo render --param n=8`).",
                ["k.Int", "k.Choice", "Polygon.regular"], (0.98,)),
    "energy": ("Energy bar chart", "A bar chart built from a polars DataFrame transitions to new data: bars grow, reorder and enter by key.",
               ["k.BarChart", "BarChart.to"], (0.3, 0.98)),
    "field": ("Vector field", "A vector field, animated stream lines and thousands of points with per-point colors, all evaluated natively.",
              ["k.VectorField", "k.StreamLines", "k.Points"], (0.3, 0.9)),
}



def load(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(f"gallery_{name}", EXAMPLES / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    index = [
        "# Examples",
        "",
        "Complete scenes from [`examples/`](../../examples). Each one passes `kinemo check --strict`",
        "and is part of the test suite. Frames below are rendered at draft quality by",
        "`scripts/build_gallery.py`.",
        "",
        "| Example | Shows |",
        "| --- | --- |",
    ]
    for name, (title, about, features, fractions) in GALLERY.items():
        scene = load(name).build()
        frames = []
        for i, fraction in enumerate(fractions):
            t = min(scene.duration - 1e-3, fraction * scene.duration)
            image = IMAGES / f"{name}_{i}.png"
            image.write_bytes(scene.builder.frame_png(t, "draft"))
            frames.append((image.name, t))
        code = (EXAMPLES / f"{name}.py").read_text(encoding="utf-8").rstrip()
        feature_list = ", ".join(f"`{f}`" for f in features)
        page = [
            f"# {title}",
            "",
            about,
            "",
            f"**Uses:** {feature_list} — see the [API reference](../reference/README.md).",
            "",
            " ".join(f"![{title} at {t:.1f} s](images/{img})" for img, t in frames),
            "",
            f"Run it: `kinemo dev examples/{name}.py` · render: `kinemo render examples/{name}.py`",
            "",
            "```python",
            code,
            "```",
            "",
        ]
        (OUT / f"{name}.md").write_text("\n".join(page), encoding="utf-8")
        index.append(f"| [{title}]({name}.md) | {about.split('. ')[0].rstrip('.')}. |")
    index.append("")
    (OUT / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(f"wrote {len(GALLERY)} examples to {OUT}")


if __name__ == "__main__":
    main()
