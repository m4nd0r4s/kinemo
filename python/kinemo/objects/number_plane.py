"""`k.NumberPlane`: a coordinate grid with basis vectors that `plane.apply(...)` deforms through
a matrix or a function, carrying the vectors, dots and shapes placed on it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Sequence, TypeVar, Unpack

from ..diagnostics import KinemoError
from ..values.color import Color
from .groups import Group
from .node import Node
from .shapes import Arrow, Dot, Polygon

if TYPE_CHECKING:
    from ..anim.animation import Animation, AnimationTiming
    from ..values.aliases import ColorLike
    from .keywords import UnplacedKeywords, UnplacedStyleKeywords

#: A map of the plane: `(x, y) -> (x', y')` in data coordinates.
PlaneMap = Callable[[float, float], tuple[float, float]]

#: `plane.apply(...)`: a 2×2 matrix (rows, `[[a, b], [c, d]]`) or a function of `(x, y)`.
PlaneTransform = Sequence[Sequence[float]] | PlaneMap

NodeT = TypeVar("NodeT", bound=Node)

I_HAT = "#83C167"
J_HAT = "#FC6255"


def _identity(x: float, y: float) -> tuple[float, float]:
    return (x, y)


def _as_map(transform: PlaneTransform) -> PlaneMap:
    if callable(transform):
        return transform
    rows = [[float(v) for v in row] for row in transform]
    if len(rows) != 2 or any(len(row) != 2 for row in rows):
        raise KinemoError.make("K0105", "plane.apply takes a 2×2 matrix like [[1, 1], [0, 1]] or a function of (x, y)")
    (a, b), (c, d) = rows
    return lambda x, y: (a * x + b * y, c * x + d * y)


def _range(spec: Sequence[float]) -> tuple[float, float, float]:
    lo, hi = float(spec[0]), float(spec[1])
    step = float(spec[2]) if len(spec) > 2 else 1.0
    return lo, hi, step


class NumberPlane(Group):
    """`k.NumberPlane(x=(-7, 7, 1), y=(-4, 4, 1))`: grid lines, axes and the basis vectors
    î and ĵ. `plane.apply([[1, 1], [0, 1]])` animates the whole plane through the matrix
    (`plane.apply(fn)` for non-linear maps); the vectors, dots and polygons made with
    `plane.vector`, `plane.dot` and `plane.polygon` go along."""

    if TYPE_CHECKING:
        _plane_opts: tuple[tuple[float, float, float], tuple[float, float, float], float, int]
        _map: PlaneMap
        _lines: list[tuple[Polygon, list[tuple[float, float]]]]
        _vectors: list[tuple[Arrow, tuple[float, float]]]
        _anchored: list[tuple[Node, tuple[float, float]]]

    def __init__(
        self,
        x: Sequence[float] = (-7, 7, 1),
        y: Sequence[float] = (-4, 4, 1),
        *,
        unit: float = 1.0,
        basis: bool = True,
        samples: int = 24,
        color: ColorLike | None = None,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        object.__setattr__(self, "_plane_opts", (_range(x), _range(y), float(unit), max(2, int(samples))))
        object.__setattr__(self, "_map", _identity)
        object.__setattr__(self, "_lines", [])
        object.__setattr__(self, "_vectors", [])
        object.__setattr__(self, "_anchored", [])
        object.__setattr__(self, "_grid_color", color)
        object.__setattr__(self, "_basis", basis)
        super().__init__(**props)

    # ---- construction ----------------------------------------------------------------
    def _parts(self) -> list[Node]:
        (x0, x1, xs), (y0, y1, ys), _, samples = self._plane_opts
        grid = self.__dict__["_grid_color"] or self._scene.theme.accent
        fg = self._scene.theme.fg
        parts: list[Node] = []
        for i in range(int((x1 - x0) / xs + 1e-9) + 1):
            vx = x0 + i * xs
            on_axis = abs(vx) < 1e-9
            pts = [(vx, y0 + (y1 - y0) * k / (samples - 1)) for k in range(samples)]
            parts.append(self._polyline(pts, fg if on_axis else grid, 3.0 if on_axis else 1.5, 1.0 if on_axis else 0.55, "y_axis" if on_axis else None))
        for j in range(int((y1 - y0) / ys + 1e-9) + 1):
            vy = y0 + j * ys
            on_axis = abs(vy) < 1e-9
            pts = [(x0 + (x1 - x0) * k / (samples - 1), vy) for k in range(samples)]
            parts.append(self._polyline(pts, fg if on_axis else grid, 3.0 if on_axis else 1.5, 1.0 if on_axis else 0.55, "x_axis" if on_axis else None))
        # Axes drawn over the grid lines.
        parts.sort(key=lambda p: getattr(p, "_part", None) is not None)
        if self.__dict__["_basis"]:
            parts += [self._arrow(1.0, 0.0, Color.hex(I_HAT), "i_hat"), self._arrow(0.0, 1.0, Color.hex(J_HAT), "j_hat")]
        return parts

    def _local(self, x: float, y: float) -> tuple[float, float]:
        unit = self._plane_opts[2]
        mx, my = self._map(x, y)
        return (mx * unit, my * unit)

    def _polyline(self, pts: list[tuple[float, float]], stroke: Any, width: float, opacity: float, part: str | None) -> Polygon:
        # An open line as a polygon that walks back along itself: its points interpolate
        # pointwise, so the line bends smoothly under non-linear maps. Grid lines may run off
        # the frame when the plane deforms (`bleed`).
        there_and_back = pts + pts[-2:0:-1]
        line = Polygon((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), stroke=stroke, stroke_width=width, opacity=opacity, fill_opacity=0.0, bleed=True)
        line.set(points=[self._local(px, py) for px, py in there_and_back])
        if part is not None:
            object.__setattr__(line, "_part", part)
        self._lines.append((line, there_and_back))
        return line

    def _arrow(self, x: float, y: float, color: Any, part: str | None = None, **style: Any) -> Arrow:
        style.setdefault("stroke_width", 5.0)
        arrow = Arrow(start=self._local(0.0, 0.0), end=self._local(x, y), stroke=color, fill=color, **style)
        if part is not None:
            object.__setattr__(arrow, "_part", part)
        self._vectors.append((arrow, (x, y)))
        return arrow

    def _attach(self, node: Node) -> None:
        """Adopt an object made after the plane; it enters with the plane when that is present."""
        self._adopt(node)
        self._children_sig.set(self.children + [node])
        if self._scene._b.present(self._id, self._scene.cursor):
            self._scene._enter(node, self._scene.cursor)

    # ---- objects on the plane ------------------------------------------------------------
    def coords(self, x: float, y: float) -> tuple[float, float]:
        """Where the data point `(x, y)` is now, in the plane's own coordinates (after the
        transformations applied so far)."""
        return self._local(float(x), float(y))

    def vector(self, x: float, y: float, **style: Unpack[UnplacedStyleKeywords]) -> Arrow:
        """An arrow from the origin to `(x, y)` that the transformations carry."""
        options: dict[str, Any] = dict(style)
        color = options.pop("color", None) or self._scene.theme.fg
        arrow = self._arrow(float(x), float(y), color, **options)
        self._attach(arrow)
        return arrow

    def dot(self, x: float, y: float, *, radius: float = 0.1, **style: Unpack[UnplacedStyleKeywords]) -> Dot:
        """A dot at `(x, y)` that the transformations carry."""
        return self.add(Dot(r=radius, **style), at=(x, y))

    def polygon(self, points: Sequence[tuple[float, float]], **style: Unpack[UnplacedStyleKeywords]) -> Polygon:
        """A filled shape with data-coordinate vertices, deformed with the plane: the unit
        square `[(0, 0), (1, 0), (1, 1), (0, 1)]` shows the determinant as its area."""
        style.setdefault("fill_opacity", 0.4)
        vertices = [(float(px), float(py)) for px, py in points]
        shape = Polygon((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), **style)
        shape.set(points=[self._local(px, py) for px, py in vertices])
        self._lines.append((shape, vertices))
        self._attach(shape)
        return shape

    def add(self, obj: NodeT, *, at: tuple[float, float]) -> NodeT:
        """Put an object on the plane at the data point `at`: transformations move it (its
        shape stays as it is; use `plane.polygon` for shapes that deform)."""
        px, py = float(at[0]), float(at[1])
        lx, ly = self._local(px, py)
        obj.set(x=lx, y=ly)
        self._anchored.append((obj, (px, py)))
        self._attach(obj)
        return obj

    # ---- transformations ---------------------------------------------------------------
    def apply(self, transform: PlaneTransform, **kw: Unpack[AnimationTiming]) -> Animation:
        """Animated transformation of the plane, after the ones already applied: a matrix
        `[[a, b], [c, d]]` (î lands on `(a, c)`, ĵ on `(b, d)`) or a function `(x, y) -> (x', y')`."""
        step, before = _as_map(transform), self._map
        object.__setattr__(self, "_map", lambda x, y: step(*before(x, y)))
        return self._animate_to_map(**kw)

    def reset(self, **kw: Unpack[AnimationTiming]) -> Animation:
        """Animated return to the untransformed plane."""
        object.__setattr__(self, "_map", _identity)
        return self._animate_to_map(**kw)

    def _animate_to_map(self, **kw: Unpack[AnimationTiming]) -> Animation:
        from ..anim.animation import par

        anims: list[Animation] = []
        for shape, pts in self._lines:
            anims.append(shape.to(points=[self._local(px, py) for px, py in pts], **kw))
        origin = self._local(0.0, 0.0)
        for arrow, (vx, vy) in self._vectors:
            anims.append(arrow.to(start=origin, end=self._local(vx, vy), **kw))
        for obj, (px, py) in self._anchored:
            lx, ly = self._local(px, py)
            anims.append(obj.to(x=lx, y=ly, **kw))
        return par(*anims)
