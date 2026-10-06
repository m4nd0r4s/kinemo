"""kinemo: explanatory animations in Python, rendered by a native core.

    import kinemo as k

    @k.scene
    def hello(s: k.Scene):
        title = k.Text("Hello, kinemo").place(at="center")
        s.play(k.write(title))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._core import IR_VERSION
from .anim.animation import Animation, par, seq, stagger
from .anim.clip import clip
from .anim.ease import ease
from .anim.morph import morph
from .anim.motion import flash, follow, squash
from .anim.verbs import draw, fade_in, fade_out, grow, indicate, music, shrink, sound, write
from .component.component import Component
from .component.context import Context, context, from_context, provide
from .component.declarations import Out, Prop, field, prop
from .diagnostics import Diagnostic, KinemoError
from .events.event import Event, EventInfo, EventSource
from .events.stateful import State, integrate, simulate
from .events.when import when
from .movie import Movie, crossfade, cut, morph_cut, movie
from .objects.bar import Bar
from .objects.brace import Brace
from .objects.charts.axes import Axes, NumberLine
from .objects.charts.polar import PolarAxes
from .objects.charts.axes_vector import vector_sum
from .objects.charts.bar_chart import BarChart
from .objects.charts.pie_chart import PieChart
from .objects.charts.line_chart import LineChart
from .objects.charts.table import Table
from .objects.groups import Column, Grid, Group, Row, Stack
from .objects.boolean import intersect, subtract, union
from .objects.keywords import ArrowKeywords, ColorKeywords, PaintKeywords, RectKeywords, StyleKeywords, TextKeywords, TransformKeywords
from .objects.annotations import box, cross, encircle, strike, underline
from .objects.angles import Angle, RightAngle
from .objects.card import Card
from .objects.gauge import Gauge
from .objects.callout import Callout
from .objects.array import Array
from .objects.graphs import Graph
from .objects.bits import Bits
from .objects.matrix import Matrix, matrix_product
from .objects.icons import ICON_NAMES, Icon
from .objects.epicycles import Epicycles
from .objects.node import Node
from .objects.series_cards import EndCard, LowerThird, TitleCard
from .objects.complex_plane import ComplexPlane
from .objects.number_plane import NumberPlane
from .objects.terminal import Terminal
from .objects.reparent import reparent
from .objects.shapes import Arc, Arrow, Circle, Dot, Ellipse, Line, Path, Polygon, Rect, RoundedRect, Sector, Square, Triangle
from .objects.svg import SVG
from .objects.code import Code
from .objects.image import Image
from .objects.mass import Points, StreamLines, VectorField
from .objects.math import Math
from .objects.text import Text
from .objects.trail import Trail, trace
from .params import Bool, Choice, Float, Int, TextParam as Str
from .reactive.expr import Expr, Time, Val
from .reactive.native import (
    atan2,
    ceil,
    clamp,
    cos,
    e,
    exp,
    floor,
    interp,
    log,
    max,
    min,
    mix,
    noise,
    pi,
    piecewise,
    python,
    sin,
    smoothstep,
    sqrt,
    tan,
    tau,
    vec,
    where,
)
from .reactive.spline import spline
from .reactive.collections import ListSignal, list_signal as list
from .reactive.signal import Signal, computed, lerp, signal
from .scene.decorator import SceneDef, scene, scene_preset
from .scene.scene import Scene
from .scene.timespan import TimeSpan
from .audio.script import Script
from .audio.voice_handle import Voice
from .theme import Theme, theme, themes
from .values.color import (
    BLACK,
    BLUE,
    GRAY,
    GREEN,
    ORANGE,
    PINK,
    PURPLE,
    RED,
    TEAL,
    TRANSPARENT,
    WHITE,
    YELLOW,
    Color,
    rgb,
)
from .values.vec import Vec

__version__ = "0.14.0"

#: Global scene time in seconds (read-only signal).
time: Expr[float] = Time()

if not TYPE_CHECKING:
    # Hidden from the type checker so a misspelled `k.name` is a static error.
    def __getattr__(name: str) -> Any:
        from .diagnostics.manim import module_attribute

        hint = module_attribute(name)
        if hint is not None:
            raise hint
        raise AttributeError(f"module 'kinemo' has no attribute {name!r}")


__all__ = [
    "Points", "StreamLines", "VectorField",
    "Brace", "Image", "SVG",
    "Axes", "NumberLine", "PolarAxes", "BarChart", "LineChart", "Table", "Component", "Context", "Event", "EventInfo", "EventSource", "State", "intersect", "spline", "subtract", "union", "reparent", "Code", "Math", "morph", "Movie", "crossfade", "cut", "morph_cut", "movie", "ListSignal", "list", "flash", "follow", "squash", "Trail", "trace", "integrate", "simulate", "when", "Out", "Prop", "clip", "context", "field", "from_context",
    "prop", "provide", "Terminal", "box", "cross", "encircle", "strike", "underline", "Angle", "RightAngle", "Card", "Gauge", "Callout", "Array", "NumberPlane", "Graph", "scene_preset", "EndCard", "LowerThird", "TitleCard", "Bits", "Matrix", "matrix_product", "PieChart", "Sector", "vector_sum", "ICON_NAMES", "Icon", "ComplexPlane", "Epicycles",
    "ArrowKeywords", "ColorKeywords", "PaintKeywords", "RectKeywords", "StyleKeywords", "TextKeywords", "TransformKeywords",
    "Animation", "Arc", "Arrow", "BLACK", "BLUE", "Bar", "Bool", "Choice", "Circle", "Color", "Column",
    "Diagnostic", "Dot", "Ellipse", "Expr", "Float", "GRAY", "GREEN", "Grid", "Group", "IR_VERSION", "Int",
    "KinemoError", "Line", "Node", "ORANGE", "PINK", "PURPLE", "Path", "Polygon", "RED", "Rect", "RoundedRect",
    "Row", "Scene", "SceneDef", "Signal", "Square", "Stack", "Str", "TEAL", "TRANSPARENT", "Text", "Theme",
    "TimeSpan", "Triangle", "Val", "Vec", "Voice", "Script", "WHITE", "YELLOW", "atan2", "ceil", "clamp", "computed", "cos",
    "draw", "e", "ease", "exp", "fade_in", "fade_out", "floor", "grow", "indicate", "interp", "lerp", "log",
    "max", "min", "mix", "noise", "par", "pi", "piecewise", "python", "rgb", "scene", "seq", "shrink", "signal",
    "music", "sin", "smoothstep", "sound", "sqrt", "stagger", "tan", "tau", "theme", "themes", "time", "vec", "where",
    "write",
]
