"""`k.list`: a list signal whose mutations are recorded at the cursor."""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator, TypeVar, overload

from .._runtime.context import current_scene
from .._runtime.spans import user_span
from ..values.encode import encode
from ..diagnostics import KinemoError
from .signal import Signal

T = TypeVar("T")


class ListSignal(Signal[list[T]]):
    """Python lists are not tracked; `k.list([...])` is. Changes switch in steps."""

    __slots__ = ()

    def _current(self) -> list[T]:
        from .._runtime.context import tracing

        if tracing():
            raise KinemoError.make(
                "K0310",
                "a k.list cannot be read inside a traced function (len(), iteration, indexing)",
                fixes=[("read it in the scene body at the cursor", "len(items)"), ("or derive a count signal yourself", "count = k.signal(0)")],
            )
        value: list[T] | None = self.now
        return list(value) if value is not None else []

    def _write(self, items: list[T]) -> None:
        self._scene._push_set(self, items, user_span(3))

    def append(self, item: T) -> None:
        """Append `item` at the cursor."""
        self._write(self._current() + [item])

    def insert(self, index: int, item: T) -> None:
        """Insert `item` at `index`, at the cursor."""
        items = self._current()
        items.insert(index, item)
        self._write(items)

    def pop(self, index: int = -1) -> T:
        """Remove and return the item at `index`, at the cursor."""
        items = self._current()
        value = items.pop(index)
        self._write(items)
        return value

    def swap(self, i: int, j: int) -> None:
        """Exchange the items at `i` and `j`, at the cursor."""
        items = self._current()
        items[i], items[j] = items[j], items[i]
        self._write(items)

    def __len__(self) -> int:
        return len(self._current())

    def __iter__(self) -> Iterator[T]:
        return iter(self._current())

    def __getitem__(self, i: int) -> T:
        return self._current()[i]


@overload
def list_signal() -> ListSignal[Any]: ...
@overload
def list_signal(items: Iterable[T]) -> ListSignal[T]: ...
def list_signal(items: Iterable[Any] | None = None) -> ListSignal[Any]:
    s = current_scene()
    values = list(items or [])
    sid = s._b.add_signal(json.dumps(encode(values, "list")), "step_end", None, json.dumps(user_span().ir()))
    return ListSignal(s, sid, "list", "step_end")
