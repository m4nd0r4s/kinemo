"""Data interop: Arrow PyCapsule sources read natively (polars, pyarrow, pandas), numpy via
the buffer protocol, plain Python sequences, and K12xx diagnostics."""

from __future__ import annotations

import math
from typing import Any

import pytest

from conftest import raises_code
from kinemo import _core
from kinemo.data import arrow
from kinemo.data.arrow import Column, column, columns, to_float_list, to_str_list

pl = pytest.importorskip("polars")
np = pytest.importorskip("numpy")


def same_floats(actual: list[float], expected: list[float]) -> bool:
    return len(actual) == len(expected) and all(
        (math.isnan(a) and math.isnan(e)) or a == pytest.approx(e) for a, e in zip(actual, expected)
    )


class StreamOnly:
    """Exposes only `__arrow_c_stream__`: nothing to iterate, no `to_list`."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls = 0

    def __arrow_c_stream__(self, requested_schema: Any = None) -> Any:
        self.calls += 1
        return self.inner.__arrow_c_stream__(requested_schema)


class ArrayOnly:
    """Exposes only `__arrow_c_array__`."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls = 0

    def __arrow_c_array__(self, requested_schema: Any = None) -> Any:
        self.calls += 1
        return self.inner.__arrow_c_array__(requested_schema)


# ---- polars (reference) -------------------------------------------------------------------

def test_polars_series_of_every_numeric_type() -> None:
    for dtype in (pl.Int8, pl.Int32, pl.Int64, pl.UInt16, pl.UInt64, pl.Float32, pl.Float64):
        assert to_float_list(pl.Series([1, 2, 3], dtype=dtype)) == [1.0, 2.0, 3.0]


def test_polars_nulls_become_nan_and_empty_text() -> None:
    assert same_floats(to_float_list(pl.Series([1.5, None, 3.0])), [1.5, math.nan, 3.0])
    assert to_str_list(pl.Series(["PT", None, "ES"])) == ["PT", "", "ES"]


def test_polars_decimal_and_bool_columns() -> None:
    assert to_float_list(pl.Series(["1.25", "2.50"]).cast(pl.Decimal(10, 2))) == [1.25, 2.5]
    assert to_float_list(pl.Series([True, False])) == [1.0, 0.0]


def test_polars_series_is_read_through_the_capsule_only() -> None:
    source = StreamOnly(pl.Series("kw", [1, 2, 3]))
    assert to_float_list(source) == [1.0, 2.0, 3.0]
    assert source.calls == 1


def test_polars_dataframe_columns_keep_order_and_kind() -> None:
    df = pl.DataFrame({"pais": ["PT", "ES"], "gwh": [50, 260], "share": [0.1, None]})
    cols = columns(df)
    assert list(cols) == ["pais", "gwh", "share"]
    assert cols["pais"] == Column("pais", "str", ["PT", "ES"])
    assert cols["gwh"].floats() == [50.0, 260.0]
    assert same_floats(cols["share"].floats(), [0.1, math.nan])


def test_dataframe_through_a_stream_only_wrapper() -> None:
    wrapped = StreamOnly(pl.DataFrame({"x": [1, 2], "label": ["a", "b"]}))
    cols = columns(wrapped)
    assert cols["x"].floats() == [1.0, 2.0] and cols["label"].strings() == ["a", "b"]
    assert wrapped.calls == 1


def test_chunked_polars_series_concatenates_chunks() -> None:
    series = pl.concat([pl.Series([1, 2]), pl.Series([3])], rechunk=False)
    assert series.n_chunks() == 2
    assert to_float_list(series) == [1.0, 2.0, 3.0]


def test_numeric_columns_as_text_are_compact() -> None:
    assert to_str_list(pl.Series([2020, 2024])) == ["2020", "2024"]
    assert to_str_list(pl.Series([1.5, 0.25])) == ["1.5", "0.25"]


# ---- pyarrow and pandas ---------------------------------------------------------------------

def test_pyarrow_arrays_chunked_arrays_and_tables() -> None:
    pa = pytest.importorskip("pyarrow")
    assert same_floats(to_float_list(pa.array([1, None, 3])), [1.0, math.nan, 3.0])
    assert to_float_list(pa.chunked_array([[1, 2], [3]])) == [1.0, 2.0, 3.0]
    assert to_str_list(pa.array(["a", None], type=pa.large_string())) == ["a", ""]
    cols = columns(pa.table({"a": [1, 2], "b": ["x", "y"]}))
    assert cols["a"].floats() == [1.0, 2.0] and cols["b"].strings() == ["x", "y"]


def test_pyarrow_array_through_the_c_array_capsule() -> None:
    pa = pytest.importorskip("pyarrow")
    source = ArrayOnly(pa.array([4.0, 5.0]))
    assert to_float_list(source) == [4.0, 5.0]
    assert source.calls == 1


def test_pyarrow_dictionary_and_decimal() -> None:
    pa = pytest.importorskip("pyarrow")
    import decimal

    assert to_str_list(pa.array(["PT", "ES", "PT"]).dictionary_encode()) == ["PT", "ES", "PT"]
    assert to_float_list(pa.array([decimal.Decimal("1.25")])) == [1.25]


def test_pandas_dataframe_via_capsule() -> None:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    df = pd.DataFrame({"pais": ["PT", "ES"], "gwh": [50.0, None]})
    cols = columns(df)
    assert cols["pais"].strings() == ["PT", "ES"]
    assert same_floats(cols["gwh"].floats(), [50.0, math.nan])


# ---- numpy and plain Python -------------------------------------------------------------------

def test_numpy_arrays_via_buffer_protocol() -> None:
    assert to_float_list(np.arange(4, dtype=np.int64)) == [0.0, 1.0, 2.0, 3.0]
    assert to_float_list(np.array([0.5, 1.5], dtype=np.float32)) == [0.5, 1.5]
    assert to_float_list(np.linspace(0, 1, 5)[::2]) == [0.0, 0.5, 1.0]


def test_numpy_two_dimensional_array_is_not_a_column() -> None:
    with raises_code("K1203"):
        to_float_list(np.zeros((2, 2)))


def test_plain_sequences_dicts_and_rows() -> None:
    assert same_floats(to_float_list([1, None, 2.5]), [1.0, math.nan, 2.5])
    assert to_float_list(range(3)) == [0.0, 1.0, 2.0]
    assert to_str_list(("a", 1, 2.0)) == ["a", "1", "2"]
    cols = columns({"pais": ["PT", "ES"], "gwh": [1, 2]})
    assert cols["pais"].kind == "str" and cols["gwh"].kind == "float"
    rows = columns([{"pais": "PT", "gwh": 1}, {"pais": "ES"}])
    assert same_floats(rows["gwh"].floats(), [1.0, math.nan])
    mixed = columns({"n": np.array([1.0, 2.0]), "s": pl.Series(["a", "b"])})
    assert mixed["n"].floats() == [1.0, 2.0] and mixed["s"].strings() == ["a", "b"]


# ---- diagnostics ------------------------------------------------------------------------------

def test_unsupported_object_is_k1201_with_its_type() -> None:
    class Legacy:
        pass

    with raises_code("K1201") as info:
        to_float_list(Legacy())
    assert "Legacy" in info.value.diagnostic.message


def test_pandas_without_capsule_suggests_polars() -> None:
    fake = type("DataFrame", (), {"__module__": "pandas.core.frame"})()
    with raises_code("K1201") as info:
        columns(fake)
    assert any("pl.from_pandas" in (f.code or "") for f in info.value.diagnostic.fixes)


def test_missing_column_is_k1202_with_a_suggestion() -> None:
    with raises_code("K1202") as info:
        column(pl.DataFrame({"gwh": [1]}), "gw")
    assert "gwh" in info.value.diagnostic.fixes[0].description


def test_text_column_as_numbers_is_k1203() -> None:
    with raises_code("K1203"):
        columns(pl.DataFrame({"pais": ["PT"]}))["pais"].floats()
    with raises_code("K1203"):
        to_float_list(pl.Series(["PT"]))


def test_native_functions_are_exposed() -> None:
    assert _core.arrow_supported(pl.Series([1])) and not _core.arrow_supported([1])
    names = [name for name, _, _ in _core.arrow_table_columns(pl.DataFrame({"a": [1], "b": ["x"]}))]
    assert names == ["a", "b"]
    assert arrow.is_arrow(pl.DataFrame({"a": [1]}))
