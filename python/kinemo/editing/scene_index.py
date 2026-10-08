"""The call sites of a built scene: every user call a span points at (constructors,
`.set`/`.to`, `.place`, `s.play`, verbs), with its arguments and the type of value each
parameter takes, as JSON for the preview.

The preview looks a site up by the span it already has (a prop's source, a timeline bar)
and offers the literal arguments for editing, each with a widget fit for its type.
"""

from __future__ import annotations

import inspect
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .._runtime.spans import Span
from .call_sites import CallSite, Offset, SourceFile, Variable
from .value_types import ValueType, from_prop_spec, parameter_types

if TYPE_CHECKING:
    from ..objects.node import Node
    from ..scene.scene import Scene
    from ..theme.tokens import Theme
    from ..values.color import Color

#: Props whose value is a fraction (number editors clamp them).
_FRACTIONS = {"opacity", "fill_opacity", "stroke_opacity"}


def span_key(span: Span | Mapping[str, Any]) -> str:
    """Key of a span, the same the preview computes from a span's JSON."""
    if isinstance(span, Span):
        return f"{span.file}:{span.line}:{span.col}:{span.end_line}:{span.end_col}"
    return f"{span['file']}:{span['line']}:{span.get('col', 0)}:{span.get('end_line', 0)}:{span.get('end_col', 0)}"


def span_of(data: Mapping[str, Any]) -> Span:
    return Span(data["file"], int(data["line"]), int(data.get("col", 0)), int(data.get("end_line", 0)), int(data.get("end_col", 0)))


@dataclass
class IndexedSite:
    source: SourceFile
    site: CallSite
    #: Positional index → parameter name (constructors), so `k.Square(1.6)` edits `side`.
    params: tuple[tuple[int, str], ...] = ()
    #: Keywords the call accepts when absent (a default prop can be added); `None` = unknown.
    accepts: frozenset[str] | None = None
    runs: int = 1
    #: Parameter name → the kind of value it takes.
    types: dict[str, ValueType] = field(default_factory=lambda: dict[str, ValueType]())
    #: Parameters a tool may add when the call omits them, with the value they default to
    #: (`s.play(..., duration=1.0, ease=k.ease.smooth)`).
    defaults: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass
class SceneIndex:
    sites: dict[str, IndexedSite] = field(default_factory=lambda: dict[str, IndexedSite]())
    #: Palette and theme colors (`"RED"`, `"theme.accent"`) → `#rrggbb`.
    colors: dict[str, str] = field(default_factory=lambda: dict[str, str]())

    def json(self) -> dict[str, Any]:
        return {key: _site_json(entry, self.colors) for key, entry in self.sites.items()}


def index_scene(scene: "Scene", ir: Mapping[str, Any], sources: Mapping[str, SourceFile]) -> SceneIndex:
    """Index every span of the scene that covers a call in one of `sources` (path → file)."""
    counts: Counter[str] = Counter()
    spans: dict[str, Span] = {}
    constructors: dict[str, "Node"] = {}
    #: Span key → the type whose method the call is (a node class, the scene, `Signal`).
    owners: dict[str, type] = {}
    nodes = {node._id: node for node in scene._nodes}  # pyright: ignore[reportPrivateUsage]

    def note(span: Span | None, owner: type | None = None, counted: bool = True) -> None:
        if span is None or not span.end_line or span.file not in sources:
            return
        key = span_key(span)
        spans[key] = span
        if owner is not None:
            owners.setdefault(key, owner)
        if counted:
            counts[key] += 1

    for node in scene._nodes:  # pyright: ignore[reportPrivateUsage]
        # Parts (a text's glyph runs) are built inside the call that made their owner.
        is_part = node._part is not None  # pyright: ignore[reportPrivateUsage]
        note(node._span, counted=not is_part)  # pyright: ignore[reportPrivateUsage]
        if not is_part:
            constructors.setdefault(span_key(node._span), node)  # pyright: ignore[reportPrivateUsage]
    for entry in scene._log:  # pyright: ignore[reportPrivateUsage]
        note(entry.span)
        note(entry.call, owner=type(scene))
    for obj in ir.get("objects", []):
        for place in obj.get("place", []):
            if "span" in place:
                node = nodes.get(obj["id"])
                note(span_of(place["span"]), owner=type(node) if node is not None else None)
    from ..reactive.signal import Signal

    for signal in ir.get("signals", []):
        owned = nodes.get(signal["owner"][0]) if signal.get("owner") else None
        owner = type(owned) if owned is not None else Signal
        for item in signal.get("timeline", []):
            if "span" in item:
                note(span_of(item["span"]), owner=owner, counted=False)

    index = SceneIndex(colors=palette_colors(scene.theme))
    for key, span in spans.items():
        source = sources[span.file]
        site = source.call_at(span)
        if site is None:
            continue
        node = constructors.get(key)
        factory = node.__dict__.get("_factory") if node is not None else None
        if factory is not None:
            # `ax.vline(4)`: the call is the method that made the object, not its constructor.
            params, accepts = _positional_params(factory), _factory_accepts(factory, node)
            types = {**_prop_types(type(node)), **_types_of(factory)} if node is not None else _types_of(factory)
            defaults = _insertable_defaults(factory, types)
            index.sites[key] = IndexedSite(source, site, params, accepts, max(counts[key], 1), types, defaults)
            continue
        fn = _site_callable(site, source, node, owners.get(key))
        params, accepts = _constructor_binding(node) if node is not None else (_positional_params(fn), None)
        types = _site_types(fn, node, owners.get(key))
        defaults = _insertable_defaults(fn, types) if node is None else {}
        if node is None and defaults:
            accepts = frozenset(defaults)
        index.sites[key] = IndexedSite(source, site, params, accepts, max(counts[key], 1), types, defaults)
    return index


def _site_callable(site: CallSite, source: SourceFile, constructed: "Node | None", owner: type | None) -> Callable[..., Any] | None:
    """What the call calls: a constructor, a method of the object (or scene) it belongs to,
    or a kinemo function (`k.fade_in`)."""
    if constructed is not None:
        return type(constructed).__init__
    prefix, _, name = site.callee.rpartition(".")
    if prefix in source.module_aliases:
        # A kinemo function (`k.fade_in(dot)`), even though the items it writes belong to dot.
        import kinemo

        found = getattr(kinemo, name, None)
        return found if callable(found) else None
    if owner is not None:
        return getattr(owner, name, None)
    return None


def _site_types(fn: Callable[..., Any] | None, constructed: "Node | None", owner: type | None) -> dict[str, ValueType]:
    from ..objects.node import Node

    if constructed is not None:
        return {**_prop_types(type(constructed)), **_types_of(fn)}
    if owner is not None and issubclass(owner, Node):
        return {**_prop_types(owner), **_types_of(fn)}
    return _types_of(fn)


def _positional_params(fn: Callable[..., Any] | None) -> tuple[tuple[int, str], ...]:
    """Positional index → parameter name of a function or method (`self` left out)."""
    if fn is None:
        return ()
    try:
        parameters = list(inspect.signature(inspect.unwrap(fn)).parameters.values())
    except (TypeError, ValueError):
        return ()
    if parameters and parameters[0].name == "self":
        parameters = parameters[1:]
    positional = [p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return tuple((i, p.name) for i, p in enumerate(positional))


def _insertable_defaults(fn: Callable[..., Any] | None, types: Mapping[str, ValueType]) -> dict[str, object]:
    """Optional parameters a tool may add, with what they default to. `None` defaults mean
    "the usual value" for timing (one second, the smooth curve) and are left out otherwise."""
    from ..anim.animation import DEFAULT_DURATION
    from ..anim.ease import Ease

    try:
        signature = inspect.signature(inspect.unwrap(fn)) if fn is not None else None
    except (TypeError, ValueError):
        signature = None
    out: dict[str, object] = {}
    for parameter in signature.parameters.values() if signature else ():
        if parameter.name not in types or parameter.default is inspect.Parameter.empty:
            continue
        if parameter.kind not in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY):
            continue
        default = parameter.default
        if default is None:
            default = {"duration": DEFAULT_DURATION, "ease": "ease.smooth"}.get(parameter.name)
        elif isinstance(default, Ease):
            default = f"ease.{default.kind}"
        if isinstance(default, (bool, int, float, str)):
            out[parameter.name] = default
    return out


@lru_cache(maxsize=512)
def _types_of(fn: Callable[..., Any] | None) -> dict[str, ValueType]:
    types = parameter_types(fn)
    for name in _FRACTIONS & types.keys():
        types[name] = {**types[name], "range": [0, 1]}
    return types


@lru_cache(maxsize=256)
def _prop_types(cls: type["Node"]) -> dict[str, ValueType]:
    out: dict[str, ValueType] = {}
    for name, spec in cls._all_props.items():  # pyright: ignore[reportPrivateUsage]
        kind = from_prop_spec(name, spec)
        if kind is not None:
            out[name] = kind
    if any(p in out for p in ("fill", "stroke")):
        out["color"] = {"type": "color"}
    return out


def _factory_accepts(factory: Callable[..., Any], node: "Node | None") -> frozenset[str] | None:
    """Keywords the factory method takes; its `**style` takes the made object's props."""
    try:
        parameters = list(inspect.signature(inspect.unwrap(factory)).parameters.values())[1:]  # self
    except (TypeError, ValueError):
        return None
    accepts = {p.name for p in parameters if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
    if node is not None and any(p.kind is p.VAR_KEYWORD for p in parameters):
        accepts.update(type(node)._all_props)  # pyright: ignore[reportPrivateUsage]
        if node._color_props():  # pyright: ignore[reportPrivateUsage]
            accepts.add("color")
    return frozenset(accepts)


def _constructor_binding(node: "Node") -> tuple[tuple[tuple[int, str], ...], frozenset[str] | None]:
    try:
        signature = inspect.signature(type(node).__init__)
    except (TypeError, ValueError):
        return (), None
    parameters = list(signature.parameters.values())[1:]  # self
    positional = [p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    params = tuple((i, p.name) for i, p in enumerate(positional))
    accepts = {p.name for p in parameters if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
    if any(p.kind is p.VAR_KEYWORD for p in parameters):
        accepts.update(type(node)._all_props)  # pyright: ignore[reportPrivateUsage]
        if node._color_props():  # pyright: ignore[reportPrivateUsage]
            accepts.add("color")
    return params, frozenset(accepts)


def palette_colors(theme: "Theme") -> dict[str, str]:
    """The named colors (`k.RED`, ...) and the theme's tokens (`k.theme.accent`, resolved for
    this scene's theme), as `#rrggbb`."""
    import kinemo

    from ..values.color import Color

    named = [(name, value) for name, value in vars(kinemo).items() if name.isupper() and isinstance(value, Color) and value.a > 0]
    named.sort(key=lambda item: _swatch_order(item[1]))
    out = {name: value.to_hex() for name, value in named}
    for name in ("fg", "bg", "accent", "muted", "secondary"):
        token = getattr(theme, name, None)
        if isinstance(token, Color):
            out[f"theme.{name}"] = token.to_hex()
    return out


def _swatch_order(color: "Color") -> tuple[int, float]:
    """Colors by hue, then the grays from light to dark."""
    import colorsys

    hue, lightness, saturation = colorsys.rgb_to_hls(color.r, color.g, color.b)
    return (1, -lightness) if saturation < 0.15 else (0, hue)


def easing_names() -> list[str]:
    """The ready-made curves of `k.ease` (the ones written without arguments)."""
    from ..anim.ease import Ease, ease

    return [name for name, value in vars(type(ease)).items() if isinstance(value, Ease)]


def _offset_json(offset: "Offset | None") -> dict[str, int] | None:
    return {"number": offset.number, "sign": offset.sign} if offset is not None else None


def _variable_json(variable: "Variable", colors: Mapping[str, str]) -> dict[str, Any]:
    return {
        "name": variable.name,
        "text": variable.text,
        "kind": variable.kind,
        "value": variable.value,
        "line": variable.line,
        "uses": variable.uses,
        **({"hex": colors.get(str(variable.value))} if variable.kind == "color" else {}),
    }


def _site_json(entry: IndexedSite, colors: Mapping[str, str]) -> dict[str, Any]:
    params = dict(entry.params)
    aliases = sorted(entry.source.module_aliases)
    shown: set[str] = set(entry.accepts or ())
    for a in entry.site.arguments:
        name = a.keyword or (params.get(a.index) if a.index is not None else None)
        if name:
            shown.add(name)
    return {
        "callee": entry.site.callee,
        "line": entry.site.start.line,
        "runs": entry.runs,
        "alias": aliases[0] if aliases else None,
        "accepts": sorted(entry.accepts) if entry.accepts is not None else None,
        "types": {name: kind for name, kind in entry.types.items() if name in shown},
        "defaults": entry.defaults,
        "arguments": [
            {
                "keyword": a.keyword,
                "index": a.index,
                "param": a.keyword or (params.get(a.index) if a.index is not None else None),
                "text": a.text,
                "kind": a.kind,
                "value": a.value,
                **({"hex": colors.get(str(a.value))} if a.kind == "color" else {}),
                **({"numbers": [{"text": n.text, "value": n.value, "offset": n.offset} for n in a.numbers]} if a.numbers else {}),
                **({"variable": _variable_json(a.variable, colors)} if a.variable is not None else {}),
                **({"offset": _offset_json(a.offset)} if a.offset is not None else {}),
                **({"offsets": [_offset_json(o) for o in a.offsets]} if a.offsets else {}),
            }
            for a in entry.site.arguments
        ],
    }
