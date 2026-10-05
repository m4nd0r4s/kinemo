"""`k.Terminal`: a terminal or REPL window. Commands are typed after a prompt as `k.Code`
(syntax colors, `k.morph` between versions), output arrives as plain lines, and the window
grows row by row, scrolling up when it is full."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.ease import Ease, ease as eases
from ..anim.verbs import Write
from ..diagnostics import KinemoError
from ..values.color import Color
from .charts.data_transition import animate, set_at
from .code import Code, _palette_for
from .groups import Group, Reorder
from .keywords import TransformKeywords
from .node import Node
from .shapes import Circle, Rect, RoundedRect
from .text import Text

if TYPE_CHECKING:
    from ..scene.scene import Scene

#: Height of a row, in text sizes.
LINE_SPACING = 1.55
#: Characters typed per second when `type()` gets no duration.
TYPING_SPEED = 22.0
#: Seconds an output row takes to appear.
OUTPUT_DURATION = 0.3
#: The three dots of the window bar (close, minimize, zoom).
DOT_COLORS = ("#FF5F57", "#FEBC2E", "#28C840")


class Terminal(Group):
    """`k.Terminal(title="zsh", prompt="$ ", lang="bash", width=8, rows=8)`: a window whose
    `type(command)` types a command after the prompt (as `k.Code`) and `output(text)` prints
    lines; older rows scroll up once `rows` are shown. `term.lines` are the rows, oldest first
    (an input row is a group of its prompt and its code: `term.lines[0].code`)."""

    if TYPE_CHECKING:
        _terminal_opts: tuple[str, str, str, float, int, float, str, bool, bool]
        #: The window: frame, bar dots and title.
        frame: RoundedRect
        dots: list[Circle]
        title: Text
        #: The blinking caret at the end of the line being typed.
        caret: Rect
        #: Rows on screen, oldest first: input rows (`row.prompt`, `row.code`) and output `k.Text`.
        lines: list[Node]
        _rows_added: int

    def __init__(
        self,
        *,
        title: str = "",
        prompt: str = "$ ",
        lang: str = "bash",
        width: float = 8.0,
        rows: int = 8,
        size: float = 0.28,
        theme: str = "auto",
        chrome: bool = True,
        caret: bool = True,
        **props: Unpack[TransformKeywords],
    ) -> None:
        from .._runtime.context import current_scene

        if rows < 1:
            raise KinemoError.make("K0105", f"k.Terminal needs at least one row, got rows={rows}", fixes=[("show a few rows", "rows=6")])
        palette = _palette_for(current_scene().theme) if theme == "auto" else theme
        object.__setattr__(self, "_terminal_opts", (title, prompt, lang, float(width), int(rows), float(size), palette, chrome, caret))
        object.__setattr__(self, "lines", [])
        object.__setattr__(self, "dots", [])
        object.__setattr__(self, "_rows_added", 0)
        super().__init__(**props)

    # ---- geometry ----------------------------------------------------------------------
    @property
    def _line_height(self) -> float:
        return self._terminal_opts[5] * LINE_SPACING

    @property
    def _bar_height(self) -> float:
        return self._terminal_opts[5] * 2.0 if self._terminal_opts[7] else 0.0

    @property
    def _height(self) -> float:
        _, _, _, _, rows, size, _, _, _ = self._terminal_opts
        return self._bar_height + rows * self._line_height + size * 1.2

    def _left(self) -> float:
        return -self._terminal_opts[3] / 2 + self._terminal_opts[5] * 1.1

    def _slot_y(self, slot: int) -> float:
        """Vertical position of the `slot`-th visible row (0 at the top)."""
        top = self._height / 2 - self._bar_height - self._terminal_opts[5] * 0.6
        return top - (slot + 0.5) * self._line_height

    def _colors(self) -> tuple[Color, Color, Color]:
        """(window fill, text, dim text) for the palette."""
        if self._terminal_opts[6] == "light":
            return Color.hex("#F6F7F9"), Color.hex("#1F2329"), Color.hex("#6B7280")
        return Color.hex("#0D0E12"), Color.hex("#E6E8EC"), Color.hex("#7D8490")

    # ---- construction ------------------------------------------------------------------
    def _parts(self) -> list[Node]:
        title, _, _, width, _, size, _, chrome, caret = self._terminal_opts
        fill, text, dim = self._colors()
        frame = RoundedRect(w=width, h=self._height, radius=size * 0.6, fill=fill, fill_opacity=1.0, stroke=dim, stroke_width=1.5)
        self._name_part(frame, "frame")
        parts: list[Node] = [frame]
        if chrome:
            bar_y = self._height / 2 - self._bar_height / 2
            for i, color in enumerate(DOT_COLORS):
                dot = Circle(r=size * 0.2, fill=Color.hex(color), fill_opacity=1.0, stroke_width=0.0, x=-width / 2 + size * (0.9 + 0.75 * i), y=bar_y)
                self._name_part(dot, f".dots[{i}]")
                self.dots.append(dot)
                parts.append(dot)
            label = Text(title, size=size * 0.85, fill=dim, y=bar_y)
            self._name_part(label, "title")
            parts.append(label)
        cursor = Rect(w=size * 0.55, h=size * 1.15, fill=text, fill_opacity=1.0, stroke_width=0.0, visible=False)
        if caret:
            # Blinks twice a second while it is shown.
            from .. import floor, time, where

            cursor.set(opacity=lambda: where(floor(time() * 2.0) % 2.0 < 1.0, 1.0, 0.0))
        self._name_part(cursor, "caret")
        parts.append(cursor)
        return parts

    def _name_part(self, node: Node, part: str) -> None:
        object.__setattr__(node, "_part", part)
        if not part.startswith("."):
            object.__setattr__(self, part, node)

    # ---- transitions ---------------------------------------------------------------------
    def type(self, command: str, *, duration: float | None = None, cps: float = TYPING_SPEED) -> Animation:
        """Type `command` after the prompt, character by character (`cps` per second, or over
        `duration`), as `k.Code` in the terminal's language; the caret follows the typing."""
        text = command.rstrip("\n")
        seconds = duration if duration is not None else max(0.2, len(text) / max(cps, 1e-6))
        return _TerminalStep(self, f"type({text[:24]!r})", seconds, lambda s, t0, d, sp: self._type(s, t0, d, sp, text), user_span())

    def output(self, text: str, *, stagger: float = 0.0, duration: float | None = None) -> Animation:
        """Print `text` below, one row per line (all at once, or `stagger` seconds apart)."""
        lines = text.rstrip("\n").split("\n") if text else [""]
        appear = OUTPUT_DURATION if duration is None else duration
        seconds = appear + stagger * (len(lines) - 1)
        return _TerminalStep(self, f"output({len(lines)} line(s))", seconds, lambda s, t0, d, sp: self._output(s, t0, d, sp, lines, stagger, appear), user_span())

    def clear(self, *, duration: float = 0.3) -> Animation:
        """Remove every row (they fade out); the next row starts at the top."""
        return _TerminalStep(self, "clear()", duration, lambda s, t0, d, sp: self._clear(s, t0, d, sp), user_span())

    # ---- what the transitions do when scheduled ------------------------------------------
    def _add_row(self, s: "Scene", row: Node, start: float, duration: float, span: Span, scroll_limit: float | None = None) -> None:
        """Put `row` in the next slot, scrolling older rows up when the window is full."""
        rows = self._terminal_opts[4]
        object.__setattr__(row, "_part", f".lines[{len(self.lines)}]")
        self._adopt(row)
        self.lines.append(row)
        object.__setattr__(self, "_rows_added", self._rows_added + 1)
        Reorder(self, self._children_at(start) + [row], span)._emit(s, start, 0.0, eases.linear)
        s._enter(row, start)
        overflow = len(self.lines) - rows
        if overflow > 0:
            gone = self.lines[:overflow]
            del self.lines[:overflow]
            # A scroll ends before the next row can start another one.
            scroll = min(duration, 0.25, scroll_limit if scroll_limit is not None else 0.25)
            animate(s, [(r._sig("y"), self._slot_y(i)) for i, r in enumerate(self.lines)], start, scroll, eases.smooth, span)
            animate(s, [(r._sig("opacity"), 0.0) for r in gone], start, scroll, eases.smooth, span)
            for r in gone:
                s._exit(r, start + scroll)
            for i, r in enumerate(self.lines):
                object.__setattr__(r, "_part", f".lines[{i}]")

    def _type(self, s: "Scene", start: float, duration: float, span: Span, text: str) -> None:
        _, prompt, lang, _, _, size, palette, _, _ = self._terminal_opts
        _, _, dim = self._colors()
        y = self._slot_y(min(len(self.lines), self._terminal_opts[4] - 1))
        # Rows are laid out from their left edge: each part sits at half its width from it.
        mark = Text(prompt.rstrip() or " ", size=size, fill=dim, mono=True)
        mark.set(x=mark.width.now / 2)
        code = Code(text or " ", lang=lang, theme=palette, size=size)
        code_left = mark.width.now + size * 0.45
        code.set(x=code_left + code.width.now / 2)
        row = Group(mark, code, x=self._left(), y=y)
        object.__setattr__(row, "prompt", mark)
        object.__setattr__(row, "code", code)
        object.__setattr__(mark, "_part", "prompt")
        object.__setattr__(code, "_part", "code")
        self._add_row(s, row, start, duration, span)
        Write([code], None, None, 0.0, span)._emit(s, start, duration, eases.linear)
        # The caret moves along the line as it is typed (monospace: one advance per character).
        left = self._left() + code_left
        caret = self.caret
        set_at(s, [(caret._sig("y"), y), (caret._sig("visible"), True)], start, span)
        s._enter(caret, start)
        # The caret's center: half its width past the last typed character.
        half = size * 0.55 / 2
        set_at(s, [(caret._sig("x"), left + half)], start, span)
        animate(s, [(caret._sig("x"), left + code.width.now + size * 0.12 + half)], start, duration, eases.linear, span)

    def _output(self, s: "Scene", start: float, duration: float, span: Span, lines: list[str], stagger: float, appear: float) -> None:
        size = self._terminal_opts[5]
        _, text_color, _ = self._colors()
        set_at(s, [(self.caret._sig("visible"), False)], start, span)
        scale = duration / max(appear + stagger * (len(lines) - 1), 1e-9)
        gap = stagger * scale
        if gap <= 0:
            # Printed at once: lines that would scroll off at the same instant are never seen.
            lines = lines[-self._terminal_opts[4]:]
            fade = duration
        else:
            # Each line finishes appearing (and scrolling) before the next one arrives.
            fade = min(appear * scale, gap)
        for i, line in enumerate(lines):
            t = start + i * gap
            slot = min(len(self.lines), self._terminal_opts[4] - 1)
            row = Text(line or " ", size=size, fill=text_color, mono=True, y=self._slot_y(slot), opacity=0.0)
            row.set(x=self._left() + row.width.now / 2)
            self._add_row(s, row, t, fade, span, gap if gap > 0 else None)
            animate(s, [(row._sig("opacity"), 1.0)], t, fade, eases.smooth, span)

    def _clear(self, s: "Scene", start: float, duration: float, span: Span) -> None:
        animate(s, [(r._sig("opacity"), 0.0) for r in self.lines], start, duration, eases.smooth, span)
        for r in self.lines:
            s._exit(r, start + duration)
        set_at(s, [(self.caret._sig("visible"), False)], start, span)
        self.lines.clear()


class _TerminalStep(Animation):
    """One step of a terminal (type, output, clear): its rows are made when it is scheduled,
    so consecutive steps follow each other."""

    def __init__(self, owner: Terminal, label: str, duration: float, apply: "_Apply", span: Span) -> None:
        super().__init__(duration, None, 0.0, span)
        self.owner = owner
        self.label = label
        self.apply = apply

    def describe(self) -> str:
        return f"{self.owner._label()}.{self.label}"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        self.apply(s, start, duration, self.span)


if TYPE_CHECKING:
    from typing import Callable

    _Apply = Callable[["Scene", float, float, Span], None]
