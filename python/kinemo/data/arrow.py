"""Columns and tables from Arrow-compatible objects, without importing any data library.

Any object implementing the Arrow PyCapsule Interface (`__arrow_c_array__` or
`__arrow_c_stream__`: polars, pandas >= 2.2, pyarrow, duckdb) is read by the native core
straight from its Arrow buffers. 1-D numpy arrays enter through the buffer protocol.
Plain lists, tuples, dicts of lists and lists of dicts work for small cases."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import GeneratorType
from typing import Any, Mapping, Protocol, Sequence, Union

from .. import _core
from ..diagnostics import KinemoError


class ArrowArrayExportable(Protocol):
    """An object exporting one Arrow array (`__arrow_c_array__`), e.g. a pyarrow array."""

    def __arrow_c_array__(self, *args: Any, **kwargs: Any) -> object: ...


class ArrowStreamExportable(Protocol):
    """An object exporting an Arrow stream (`__arrow_c_stream__`): polars and pandas
    series and frames, pyarrow tables, duckdb relations."""

    def __arrow_c_stream__(self, *args: Any, **kwargs: Any) -> object: ...


class SupportsBuffer(Protocol):
    """A 1-D array read through the buffer protocol (numpy)."""

    def __buffer__(self, flags: int, /) -> memoryview: ...


#: A column of numbers: an Arrow column, a 1-D numpy array or a plain sequence.
FloatColumn = Union[Sequence[float], ArrowArrayExportable, ArrowStreamExportable, SupportsBuffer]
#: A column of numbers or texts.
DataColumn = Union[Sequence[object], ArrowArrayExportable, ArrowStreamExportable, SupportsBuffer]
#: A table: an Arrow table (polars/pandas DataFrame, pyarrow Table, duckdb relation), a
#: dict of columns or a list of rows.
DataTable = Union[ArrowStreamExportable, ArrowArrayExportable, Mapping[str, DataColumn], Sequence[Mapping[str, object]]]

#: Column kinds: numbers (nulls are NaN) or text (nulls are None).
FLOAT = "float"
STR = "str"


@dataclass(frozen=True)
class Column:
    """A named column already read into Python values."""

    name: str
    kind: str
    values: list[Any]

    def __len__(self) -> int:
        return len(self.values)

    def floats(self) -> list[float]:
        if self.kind == FLOAT:
            return list(self.values)
        raise KinemoError.make(
            "K1203",
            f"column '{self.name}' holds text, not numbers",
            fixes=[("use a numeric column for the values", None)],
        )

    def strings(self) -> list[str]:
        if self.kind == STR:
            return ["" if v is None else str(v) for v in self.values]
        return [number_text(v) for v in self.values]


def number_text(v: float) -> str:
    """Compact text for a number: 2020, 1.5, 0.33 (two decimals at most); NaN is ""."""
    if math.isnan(v):
        return ""
    if v == int(v) and abs(v) < 1e15:
        return f"{int(v)}"
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---- type checks -----------------------------------------------------------------------

def is_arrow(obj: Any) -> bool:
    """Whether `obj` implements the Arrow PyCapsule Interface."""
    return bool(_core.arrow_supported(obj))


def _is_plain_sequence(obj: Any) -> bool:
    return isinstance(obj, list | tuple | range | GeneratorType)


def _type_name(obj: Any) -> str:
    cls = type(obj)
    module = cls.__module__
    return cls.__name__ if module == "builtins" else f"{module}.{cls.__qualname__}"


def _unsupported(obj: Any, what: str) -> KinemoError:
    module = type(obj).__module__.split(".")[0]
    if module == "pandas":
        fixes = [("convert to polars", "pl.from_pandas(df)"), ("or upgrade pandas to >= 2.2 (with pyarrow)", None)]
    elif module == "numpy":
        fixes = [("pass one 1-D array per column", "arr[:, 0]")]
    else:
        fixes = [("convert to polars", "pl.DataFrame(data)"), ("or pass lists: {'column': [...]}", None)]
    return KinemoError.make(
        "K1201",
        f"cannot read {what} from {_type_name(obj)}: it does not implement the Arrow PyCapsule Interface",
        fixes=fixes,
    )


def _native(fn: Any, obj: Any, what: str) -> Any:
    try:
        return fn(obj)
    except TypeError as e:
        if "unsupported:" in str(e):
            raise _unsupported(obj, what) from None
        raise KinemoError.make("K1203", f"could not read {what} from {_type_name(obj)}: {e}") from None


# ---- columns ---------------------------------------------------------------------------

def _plain_float(v: Any) -> float:
    return math.nan if v is None else float(v)


def to_float_list(col: Any) -> list[float]:
    """Arrow column (polars/pandas series, pyarrow array), numpy array or sequence → floats.
    Nulls become NaN."""
    if isinstance(col, Column):
        return col.floats()
    if _is_plain_sequence(col):
        return [_plain_float(v) for v in col]
    return list(_native(_core.arrow_column_f64, col, "a column"))


def to_str_list(col: Any) -> list[str]:
    """Arrow column or sequence → texts. Nulls become ""; numbers use `number_text`."""
    if isinstance(col, Column):
        return col.strings()
    if _is_plain_sequence(col):
        return ["" if v is None else number_text(v) if isinstance(v, float) else str(v) for v in col]
    if not is_arrow(col):
        raise _unsupported(col, "a column")
    try:
        return [number_text(v) for v in _core.arrow_column_f64(col)]
    except TypeError:
        pass  # not numeric: cast to text natively
    return ["" if v is None else v for v in _native(_core.arrow_column_str, col, "a column")]


# ---- tables ----------------------------------------------------------------------------

def _infer_column(name: str, values: Sequence[Any]) -> Column:
    if not _is_plain_sequence(values):
        try:
            return Column(name, FLOAT, to_float_list(values))
        except KinemoError as e:
            if e.diagnostic.code != "K1203":
                raise
            return Column(name, STR, to_str_list(values))
    values = list(values)
    numeric = all(v is None or (isinstance(v, int | float) and not isinstance(v, bool)) for v in values)
    if numeric:
        return Column(name, FLOAT, [_plain_float(v) for v in values])
    return Column(name, STR, [None if v is None else str(v) for v in values])


def _from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Column]:
    names: list[str] = []
    for row in rows:
        names += [n for n in row if n not in names]
    return {n: _infer_column(n, [row.get(n) for row in rows]) for n in names}


def columns(table: Any) -> dict[str, Column]:
    """Every column of a table, by name, in order.

    Accepts Arrow tables (polars/pandas DataFrame, pyarrow Table, duckdb relation),
    a dict of columns (`{"pais": [...], "gwh": [...]}`) or a list of rows (dicts)."""
    if isinstance(table, Mapping):
        return {str(n): v if isinstance(v, Column) else _infer_column(str(n), v) for n, v in table.items()}
    if isinstance(table, list | tuple) and all(isinstance(r, Mapping) for r in table):
        return _from_rows(table)
    if not is_arrow(table):
        raise _unsupported(table, "a table")
    entries = _native(_core.arrow_table_columns, table, "a table")
    return {name: Column(name, kind, values) for name, kind, values in entries}


def column(table: Any, name: str) -> Column:
    """One column of a table (see `columns`), with K1202 when it does not exist."""
    cols = table if isinstance(table, dict) and all(isinstance(c, Column) for c in table.values()) else columns(table)
    if name not in cols:
        raise missing_column(name, list(cols))
    return cols[name]


def missing_column(name: str, available: Sequence[str]) -> KinemoError:
    import difflib

    near = difflib.get_close_matches(name, available, n=1)
    fixes = [(f"did you mean '{near[0]}'?", None)] if near else []
    fixes.append((f"available columns: {', '.join(available) or '(none)'}", None))
    return KinemoError.make("K1202", f"the table has no column '{name}'", fixes=fixes)
