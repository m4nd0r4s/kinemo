# Images, SVG, braces and boolean shapes

This guide covers the objects that bring outside material into a scene, and two helpers
for annotating and building shapes:

- `k.Image` for raster images (PNG, JPEG);
- `k.SVG` for vector illustrations, with every element addressable by its SVG `id`;
- `k.Brace` for a curly brace that measures one side of an object and follows it;
- `k.union`, `k.intersect` and `k.subtract` for boolean operations between shapes.

All of them are ordinary objects: they enter with a verb, take `.place`, and animate with
`.to()`.

## File paths

`k.Image` and `k.SVG` take a path. A relative path is looked up **next to the scene file**
first, then relative to the working directory, so `kinemo render scenes/intro.py` from the
project root still finds `scenes/photo.png`. A missing file is `K0105` ("file not found"),
reported at the line that loads it.

The file is read when the object is created, and rendering reads it again from the
resolved path. `kinemo dev` reloads when Python files change; after editing an image or
SVG, save the scene file (or restart `dev`) to pick up the new version.

## `k.Image`

```python
k.Image(path, width=None, height=None, **props)
```

- **Size.** Without a size, the image is 3 units tall. With `width=` or `height=`, the other
  side follows the file's aspect ratio. With both, the image is stretched to that box.
- **Animatable size.** The size lives in the props `w` and `h`: `pic.to(w=6)` resizes it.
- **Transform props** (`scale`, `rotate`, `opacity`, `x`, `y`) work as on any object.
- **Layout and morphs** treat the image as its rectangle. `pic.pixel_size` gives the file's
  size in pixels.
- **SVG export** (`kinemo render --format svg`) embeds the file.

The snippet below assumes a `photo.png` next to the scene file:

```python
import kinemo as k


@k.scene
def photo(s: k.Scene):
    pic = k.Image("photo.png", height=3).place(at="center")
    caption = k.Text("Site survey, 2026", size=0.4).place(below=pic, gap=0.3)
    s.play(k.fade_in(pic, caption))
    s.play(pic.to(scale=0.8, rotate=-5))
    s.play(pic.to(w=6))
    s.wait(0.5)
```

The caption is placed `below=pic`, so it follows the image when it scales and resizes.

## `k.SVG`

```python
k.SVG(source, height=3.0, **props)
```

`source` is a file path or inline markup (a string that starts with `<`). The import keeps
the structure of the drawing:

- each shape (`<path>`, `<rect>`, `<circle>`, ...) becomes a `k.Path` with the SVG's fill,
  stroke and stroke width;
- each `<g>` becomes a `k.Group`, with its opacity;
- the drawing is scaled to `height` units and centered on the object's position.

Elements with an `id` are addressable: `art["#motor"]` (or `art["motor"]`) returns that
object, wherever it is nested, and it animates like any other. `art.ids` lists the ids in
document order. `k.draw(art)` traces every outline, then fills it.

```python
import kinemo as k

PUMP = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <g id="motor">
    <rect id="housing" x="0" y="20" width="80" height="60" fill="#4C9BE8"/>
    <g id="shaft">
      <circle cx="40" cy="50" r="15" fill="#F2F2F2"/>
      <rect x="38" y="37" width="4" height="26" fill="#4C9BE8"/>
    </g>
  </g>
  <path id="pipe" d="M 83 50 L 197 50" fill="none" stroke="#E8645A" stroke-width="6"/>
</svg>
"""


@k.scene
def pump(s: k.Scene):
    art = k.SVG(PUMP, height=3).place(at="center")
    s.play(k.draw(art), duration=2)
    s.play(art["#pipe"].to(stroke=k.YELLOW), k.indicate(art["#motor"]))
    s.play(art["#shaft"].to(rotate=90))
    s.wait(0.5)
```

From a file, the code is the same. This assumes a `machine.svg` next to the scene, with
elements `motor`, `shaft` and `belt`:

```python
import kinemo as k


@k.scene
def machine(s: k.Scene):
    art = k.SVG("machine.svg", height=3).place(at="center")
    s.play(k.draw(art))
    s.play(art["#belt"].to(stroke=k.YELLOW), k.indicate(art["#shaft"]))
    s.wait(0.5)
```

A wrong id is `K0105`, and the fix suggests the closest one:

```
K0105 error: the SVG has no element with id 'mtor'
  fix: did you mean "#motor"?
```

Give the elements you want to animate an `id` in your drawing tool (in Inkscape, Object
Properties) and check the exported file. Unnamed elements are still drawn and can be
reached by index among their siblings (`art[2]`), but indices change when the drawing
changes.

## `k.Brace`

```python
k.Brace(target, direction="down", label=None, gap=0.1, *, depth=0.25, color=None, label_gap=0.12, **props)
```

A curly brace along one side of `target`'s box: `direction=` is `"down"`, `"up"`, `"left"`
or `"right"`, `gap` units away, with the tip pointing outward. `label=` is a string or any
object (a `k.Math`, for example) placed beyond the tip, and available as `brace.label`.
The brace outline itself is `brace.shape`.

The brace is recomputed every frame from the target's layout, so it follows the object
when the object moves or changes size:

```python
import kinemo as k


@k.scene
def braces(s: k.Scene):
    bar = k.Rect(w=3, h=0.6, fill=k.BLUE, fill_opacity=0.8).place(at="center")
    width = k.Brace(bar, "down", label="width")
    height = k.Brace(bar, "right", label=k.Math(r"h"))
    s.play(k.draw(bar), k.draw(width), k.draw(height))
    s.play(bar.to(w=6, h=1.2))
    s.play(width.label.to(color=k.YELLOW))
    s.wait(0.5)
```

## Boolean operations

```python
k.union(a, b, **style)      # covered by a or b
k.intersect(a, b, **style)  # covered by both
k.subtract(a, b, **style)   # a with b cut out
```

Each one returns a new `k.Path`, computed natively from the world outlines of `a` and `b`
**at the cursor**. The operands do not need to be in the scene, and the result does not
follow later changes to them. If you move `a` afterwards, compute the operation again. The
result takes the style of `a` unless you pass one.

```python
import kinemo as k


@k.scene
def venn(s: k.Scene):
    a = k.Circle(r=1.5, x=-0.8)
    b = k.Circle(r=1.5, x=0.8)
    either = k.union(a, b, stroke=k.WHITE, fill_opacity=0)
    only_a = k.subtract(a, b, fill=k.BLUE, fill_opacity=0.5, stroke_width=0)
    both = k.intersect(a, b, fill=k.YELLOW, fill_opacity=0.8, stroke_width=0)
    s.play(k.draw(either))
    s.play(k.fade_in(only_a))
    s.play(k.fade_in(both))
    s.wait(0.5)
```

A crescent moon is one subtraction:

```python
import kinemo as k


@k.scene
def moon(s: k.Scene):
    disk = k.Circle(1.5, fill=k.YELLOW, fill_opacity=1, stroke_width=0)
    shadow = k.Circle(1.3, x=0.8)
    crescent = k.subtract(disk, shadow)
    s.play(k.draw(crescent))
    s.wait(0.5)
```

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `K0105` | `k.Image(...)` or `k.SVG(...)`: file not found. | Relative paths start from the scene file's folder; check the name and extension. |
> | `K0105` | `k.Image`/`k.SVG` could not read the file (wrong format, broken file). | PNG or JPEG for `k.Image`; valid SVG markup for `k.SVG`. |
> | `K0105` | `art["#name"]`: the SVG has no element with that id. | Use the id the fix suggests, or list them with `art.ids`. |
> | none (stale shape) | A boolean result does not move when its operands move. | It is computed at the cursor. Compute it again after the change, or animate the result itself. |
> | `K0101` | `pic.to(...)` before the image is in the scene. | Enter it first: `s.play(k.fade_in(pic))` or `s.add(pic)`. |
> | `W1001` | A tall image or SVG leaves the safe area. | Pass `height=` (the default is 3 units), or `.place(..., clamp=True)`. |

See also: [`k.Image`](../reference/objects.md#k-image), [`k.SVG`](../reference/objects.md#k-svg),
[`k.Brace`](../reference/objects.md#k-brace), [`k.union`](../reference/objects.md#k-union),
[Objects and layout](04-objects-and-layout.md).
