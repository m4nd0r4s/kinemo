"""Media and annotation shapes: `k.Image`, `k.SVG` (parts by id) and `k.Brace`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.Image",
        "Objects",
        "Raster image (PNG or JPEG) drawn by the renderer, centered on its position. Without a "
        "size it is 3 units tall; with `width=` or `height=` the other side follows the file's "
        "aspect ratio (props `w` and `h`, animatable). Relative paths start from the folder "
        "of the scene file. Accepts `scale`, `rotate` and `opacity`; morphs and layout treat it as "
        "its rectangle, and the exported SVG embeds the file.",
        '''
import kinemo as k

@k.scene
def image(s: k.Scene):
    photo = k.Image("photo.png", height=4)
    s.play(k.fade_in(photo), photo.to(scale=0.8, rotate=-5))
''',
        related=("k.SVG", "k.morph"),
        assets=("photo.png",),
    ),
    DocEntry(
        "k.SVG",
        "Objects",
        "Imports an SVG illustration (a file or inline markup): each shape becomes a `k.Path` with "
        "the SVG's fill, stroke and stroke width, and each `<g>` becomes a `k.Group`. The "
        "drawing is scaled to be `height` units tall and centered on the position. "
        "Elements with an `id` are addressable: `svg[\"#motor\"]` returns that object, which "
        "animates like any other; `svg.ids` lists the ids.",
        '''
import kinemo as k

@k.scene
def illustration(s: k.Scene):
    machine = k.SVG("motor.svg", height=3)
    s.play(k.draw(machine))
    s.play(machine["#polia"].to(fill=k.RED), k.indicate(machine["#motor"]))
''',
        related=("k.Path", "k.Image", "k.Group"),
        assets=("motor.svg",),
    ),
    DocEntry(
        "k.Brace",
        "Objects",
        "Curly brace (`}`) along one side of an object's box: `direction=` \"down\", \"up\", "
        "\"left\" or \"right\", `gap` units away from it, with the tip pointing outward. It is "
        "recomputed every frame from the target's layout, so it follows the object when it moves or "
        "changes size. `label=` (text or an object) sits beyond the tip, as `brace.label`; the "
        "brace itself is `brace.shape`.",
        '''
import kinemo as k

@k.scene
def brace(s: k.Scene):
    bar = k.Rect(w=3, h=0.6, fill=k.BLUE, fill_opacity=0.8)
    s.play(k.draw(bar), k.draw(k.Brace(bar, "down", label="width")))
    s.play(bar.to(w=6))
''',
        related=("k.Rect", "Node.place"),
    ),
)
