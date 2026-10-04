"""Typed keyword arguments of object constructors and of `obj.to(...)` / `obj.set(...)`.

Constructors take `**props: Unpack[...Keywords]`, so every prop keyword has a type for the
type checker while the runtime keeps one generic path (`Node._init_props`). The pieces
below compose: a constructor whose own parameter reuses a prop name (`k.Axes(x=...)`,
`Triangle.right(scale=...)`) unpacks only the pieces without that name."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, TypedDict

if TYPE_CHECKING:
    from typing_extensions import TypedDict as ExtensibleTypedDict

    from typing import Sequence

    from ..anim.ease import EaseLike
    from ..reactive.signal import Blend
    from ..values.aliases import Align, Anchor, BoolVal, ColorVal, FloatsVal, FloatVal, VecVal
    from .node import Node


class IdentityKeywords(TypedDict, total=False):
    #: Name used in diagnostics and `kinemo inspect` (default: the assigned variable).
    name: str | None
    #: Stable identity across morphs and data transitions.
    key: str | None


class TranslationKeywords(TypedDict, total=False):
    x: FloatVal
    y: FloatVal
    #: Sets `x` and `y` together (a point, a vector expression or a pair).
    position: VecVal


class OrientationKeywords(TypedDict, total=False):
    rotate: FloatVal
    anchor: VecVal
    z: FloatVal


class ScaleKeywords(TypedDict, total=False):
    scale: FloatVal
    scale_x: FloatVal
    scale_y: FloatVal


class VisibilityKeywords(TypedDict, total=False):
    opacity: FloatVal
    visible: BoolVal
    bleed: BoolVal


class PaintKeywords(TypedDict, total=False):
    fill: ColorVal
    fill_opacity: FloatVal
    stroke: ColorVal
    stroke_width: FloatVal
    dash: FloatsVal


class ColorKeywords(TypedDict, total=False):
    #: Sets the stroke and the fill (text: its fill) together.
    color: ColorVal


class TransformKeywords(IdentityKeywords, TranslationKeywords, OrientationKeywords, ScaleKeywords, VisibilityKeywords, total=False):
    """Props every object has (groups, containers, charts)."""


class UnplacedKeywords(IdentityKeywords, OrientationKeywords, ScaleKeywords, VisibilityKeywords, total=False):
    """Transform props without `x`/`y`/`position` (for constructors that place by themselves)."""


class ChartKeywords(OrientationKeywords, ScaleKeywords, VisibilityKeywords, total=False):
    """Transform props of data charts, whose `x`, `y` and `key` parameters name columns."""

    name: str | None


class StyleKeywords(TransformKeywords, PaintKeywords, ColorKeywords, total=False):
    """Props of shapes and text: transform plus fill and stroke."""


class PlotStyleKeywords(TransformKeywords, total=False):
    """`ax.plot(..., **style)`: the curve's stroke comes from `color=`."""

    fill: ColorVal
    fill_opacity: FloatVal
    stroke_width: FloatVal
    dash: FloatsVal


class UnplacedStyleKeywords(UnplacedKeywords, PaintKeywords, ColorKeywords, total=False):
    """Style props without `x`/`y`/`position`."""


class UnscaledStyleKeywords(IdentityKeywords, TranslationKeywords, OrientationKeywords, VisibilityKeywords, PaintKeywords, ColorKeywords, total=False):
    """Style props without `scale` (for `Triangle.right(..., scale=)`)."""


class FieldKeywords(TransformKeywords, total=False):
    """`k.VectorField` / `k.StreamLines`: transform props plus the line width."""

    stroke_width: FloatVal
    color_low: ColorVal
    color_high: ColorVal


class RectKeywords(StyleKeywords, total=False):
    #: Corner radius.
    radius: FloatVal


class ArrowKeywords(StyleKeywords, total=False):
    #: Arrow head length.
    tip: FloatVal


class TextKeywords(StyleKeywords, total=False):
    mono: BoolVal


class PlaceKeywords(TypedDict, total=False):
    """`obj.place(...)` and `obj.to_place(...)`."""

    at: Anchor | VecVal
    above: Node
    below: Node
    left_of: Node
    right_of: Node
    inside: Node
    gap: FloatVal
    margin: FloatVal
    pad: FloatVal
    align: Align
    clamp: bool
    weak: bool
    by: str


if TYPE_CHECKING:
    # `extra_items` (PEP 728) needs typing_extensions; only the type checker reads it.

    class GroupKeywords(ExtensibleTypedDict, total=False, extra_items=object):
        """`k.Group(...)`: transform props are typed; subclasses (containers, charts,
        components) pass their own props through the same constructor."""

        name: str | None
        key: str | None
        x: FloatVal
        y: FloatVal
        position: VecVal
        rotate: FloatVal
        anchor: VecVal
        z: FloatVal
        scale: FloatVal
        scale_x: FloatVal
        scale_y: FloatVal
        opacity: FloatVal
        visible: BoolVal
        bleed: BoolVal

    class PropChanges(ExtensibleTypedDict, total=False, extra_items=object):
        """`obj.to(...)` / `obj.set(...)`: transform and style props are typed; the props of
        a particular object (`r=`, `value=`, a component's own props) are accepted too."""

        x: FloatVal
        y: FloatVal
        position: VecVal
        rotate: FloatVal
        anchor: VecVal
        z: FloatVal
        scale: FloatVal
        scale_x: FloatVal
        scale_y: FloatVal
        opacity: FloatVal
        visible: BoolVal
        bleed: BoolVal
        fill: ColorVal
        fill_opacity: FloatVal
        stroke: ColorVal
        stroke_width: FloatVal
        dash: FloatsVal
        color: ColorVal

    class ChangeKeywords(ExtensibleTypedDict, total=False, extra_items=object):
        """What a subclass's `to(...)` forwards to `Group.to`: timing, placement,
        children and props."""

        duration: float | None
        ease: EaseLike | None
        delay: float
        blend: Blend
        place: PlaceKeywords | Mapping[str, object] | None
        children: Sequence[Node] | None
        x: FloatVal
        y: FloatVal
        position: VecVal
        rotate: FloatVal
        anchor: VecVal
        z: FloatVal
        scale: FloatVal
        scale_x: FloatVal
        scale_y: FloatVal
        opacity: FloatVal
        visible: BoolVal
        bleed: BoolVal
        fill: ColorVal
        fill_opacity: FloatVal
        stroke: ColorVal
        stroke_width: FloatVal
        dash: FloatsVal
        color: ColorVal
