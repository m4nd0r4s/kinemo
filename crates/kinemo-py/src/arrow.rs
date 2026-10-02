//! Arrow PyCapsule Interface: columns and tables from any library, without importing it.
//!
//! Objects exposing `__arrow_c_array__` (an array) or `__arrow_c_stream__` (a stream of
//! arrays or record batches) are read straight from their Arrow buffers through the
//! C Data / C Stream interfaces. numpy-like arrays enter through the buffer protocol.

use std::ffi::{c_char, c_int, c_void, CStr};
use std::sync::Arc;

use arrow_array::cast::AsArray;
use arrow_array::ffi::{from_ffi, FFI_ArrowArray, FFI_ArrowSchema};
use arrow_array::types::Float64Type;
use arrow_array::{make_array, Array, ArrayRef};
use arrow_schema::{DataType, Field};
use pyo3::buffer::{Element, PyBuffer};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyCapsule, PyTuple};

const SCHEMA_CAPSULE: &CStr = c"arrow_schema";
const ARRAY_CAPSULE: &CStr = c"arrow_array";
const STREAM_CAPSULE: &CStr = c"arrow_array_stream";

/// A column read from Arrow: its field (name and type) and its chunks.
struct ArrowColumn {
    field: Field,
    chunks: Vec<ArrayRef>,
}

fn arrow_error(e: impl std::fmt::Display) -> PyErr {
    PyValueError::new_err(format!("Arrow: {e}"))
}

// ---- import through the C interfaces ------------------------------------------------

/// Imports `(schema_capsule, array_capsule)` from `__arrow_c_array__`.
fn import_array(capsules: &Bound<'_, PyAny>) -> PyResult<ArrowColumn> {
    let pair = capsules.cast::<PyTuple>()?;
    let schema_capsule = pair.get_item(0)?;
    let array_capsule = pair.get_item(1)?;
    let schema_capsule = schema_capsule.cast::<PyCapsule>()?;
    let array_capsule = array_capsule.cast::<PyCapsule>()?;
    let schema_ptr = schema_capsule.pointer_checked(Some(SCHEMA_CAPSULE))?.as_ptr() as *const FFI_ArrowSchema;
    let array_ptr = array_capsule.pointer_checked(Some(ARRAY_CAPSULE))?.as_ptr() as *mut FFI_ArrowArray;
    // SAFETY: the capsules hold valid C Data structs. `from_raw` moves the array out and
    // leaves a released struct behind, so the capsule destructor does not free it twice;
    // the schema stays owned (and released) by its capsule.
    let (schema, array) = unsafe { (&*schema_ptr, FFI_ArrowArray::from_raw(array_ptr)) };
    let field = Field::try_from(schema).map_err(arrow_error)?;
    let data = unsafe { from_ffi(array, schema) }.map_err(arrow_error)?;
    Ok(ArrowColumn { field, chunks: vec![make_array(data)] })
}

/// The C Stream interface struct (`struct ArrowArrayStream`, a stable C ABI). Owned: it
/// is released on drop.
#[repr(C)]
struct ArrowArrayStream {
    get_schema: Option<unsafe extern "C" fn(*mut ArrowArrayStream, *mut FFI_ArrowSchema) -> c_int>,
    get_next: Option<unsafe extern "C" fn(*mut ArrowArrayStream, *mut FFI_ArrowArray) -> c_int>,
    get_last_error: Option<unsafe extern "C" fn(*mut ArrowArrayStream) -> *const c_char>,
    release: Option<unsafe extern "C" fn(*mut ArrowArrayStream)>,
    private_data: *mut c_void,
}

impl ArrowArrayStream {
    /// Moves the stream out of `ptr`, marking the source released (C Stream move semantics).
    ///
    /// # Safety
    /// `ptr` must point to a valid `struct ArrowArrayStream`.
    unsafe fn take(ptr: *mut ArrowArrayStream) -> Self {
        let stream = std::ptr::read(ptr);
        (*ptr).release = None;
        stream
    }

    fn error(&mut self, code: c_int) -> PyErr {
        let message = self.get_last_error.and_then(|last_error| {
            // SAFETY: the producer returns null or a NUL-terminated message it owns.
            let ptr = unsafe { last_error(self) };
            (!ptr.is_null()).then(|| unsafe { CStr::from_ptr(ptr) }.to_string_lossy().into_owned())
        });
        arrow_error(message.unwrap_or_else(|| format!("stream error code {code}")))
    }
}

impl Drop for ArrowArrayStream {
    fn drop(&mut self) {
        if let Some(release) = self.release {
            // SAFETY: a non-released stream is released exactly once, by its owner.
            unsafe { release(self) };
        }
    }
}

/// Imports every chunk of the stream capsule from `__arrow_c_stream__`.
fn import_stream(capsule: &Bound<'_, PyAny>) -> PyResult<ArrowColumn> {
    let capsule = capsule.cast::<PyCapsule>()?;
    let ptr = capsule.pointer_checked(Some(STREAM_CAPSULE))?.as_ptr() as *mut ArrowArrayStream;
    // SAFETY: the capsule holds a valid stream; we take it over and the capsule is left
    // with a released one.
    let mut stream = unsafe { ArrowArrayStream::take(ptr) };
    let (Some(get_schema), Some(get_next)) = (stream.get_schema, stream.get_next) else {
        return Err(arrow_error("the stream was already consumed"));
    };
    if stream.release.is_none() {
        return Err(arrow_error("the stream was already consumed"));
    }
    let mut schema = FFI_ArrowSchema::empty();
    let code = unsafe { get_schema(&mut stream, &mut schema) };
    if code != 0 {
        return Err(stream.error(code));
    }
    let field = Field::try_from(&schema).map_err(arrow_error)?;
    let mut chunks = Vec::new();
    loop {
        let mut array = FFI_ArrowArray::empty();
        let code = unsafe { get_next(&mut stream, &mut array) };
        if code != 0 {
            return Err(stream.error(code));
        }
        if array.is_released() {
            break;
        }
        let data = unsafe { from_ffi(array, &schema) }.map_err(arrow_error)?;
        chunks.push(make_array(data));
    }
    Ok(ArrowColumn { field, chunks })
}

/// Reads `obj` through `__arrow_c_array__` (preferred) or `__arrow_c_stream__`.
/// `Ok(None)` when it implements neither.
fn import_arrow(obj: &Bound<'_, PyAny>) -> PyResult<Option<ArrowColumn>> {
    if obj.hasattr("__arrow_c_array__")? {
        return import_array(&obj.call_method0("__arrow_c_array__")?).map(Some);
    }
    if obj.hasattr("__arrow_c_stream__")? {
        return import_stream(&obj.call_method0("__arrow_c_stream__")?).map(Some);
    }
    Ok(None)
}

/// A column from a single-column table (a one-column DataFrame) or the column itself.
fn single_column(column: ArrowColumn) -> PyResult<ArrowColumn> {
    let DataType::Struct(fields) = column.field.data_type().clone() else { return Ok(column) };
    if fields.len() != 1 {
        let names: Vec<&str> = fields.iter().map(|f| f.name().as_str()).collect();
        return Err(PyTypeError::new_err(format!("expected one column, got a table with columns {names:?}")));
    }
    let chunks = column.chunks.iter().map(|c| c.as_struct().column(0).clone()).collect();
    Ok(ArrowColumn { field: fields[0].as_ref().clone(), chunks })
}

// ---- value conversion -----------------------------------------------------------------

fn is_numeric(data_type: &DataType) -> bool {
    match data_type {
        DataType::Dictionary(_, values) => is_numeric(values),
        DataType::Boolean | DataType::Null => true,
        other => other.is_numeric(),
    }
}

fn push_floats(chunk: &dyn Array, out: &mut Vec<f64>) -> PyResult<()> {
    let floats = arrow_cast::cast(chunk, &DataType::Float64).map_err(arrow_error)?;
    let floats = floats.as_primitive::<Float64Type>();
    if floats.null_count() == 0 {
        out.extend_from_slice(floats.values());
    } else {
        out.extend(floats.iter().map(|v| v.unwrap_or(f64::NAN)));
    }
    Ok(())
}

fn floats_of(column: &ArrowColumn) -> PyResult<Vec<f64>> {
    let data_type = column.field.data_type();
    if !is_numeric(data_type) {
        return Err(PyTypeError::new_err(format!("column '{}' is {data_type}, not numeric", column.field.name())));
    }
    let mut out = Vec::with_capacity(column.chunks.iter().map(|c| c.len()).sum());
    for chunk in &column.chunks {
        push_floats(chunk.as_ref(), &mut out)?;
    }
    Ok(out)
}

fn strings_of(column: &ArrowColumn) -> PyResult<Vec<Option<String>>> {
    let mut out = Vec::with_capacity(column.chunks.iter().map(|c| c.len()).sum());
    for chunk in &column.chunks {
        let text = arrow_cast::cast(chunk.as_ref(), &DataType::Utf8).map_err(arrow_error)?;
        out.extend(text.as_string::<i32>().iter().map(|v| v.map(str::to_owned)));
    }
    Ok(out)
}

// ---- buffer protocol (numpy) ------------------------------------------------------------

fn buffer_as<T: Element + Copy + Into<f64>>(obj: &Bound<'_, PyAny>) -> Option<PyResult<Vec<f64>>> {
    let buffer = PyBuffer::<T>::get(obj).ok()?;
    if buffer.dimensions() != 1 {
        return Some(Err(PyTypeError::new_err(format!("expected a 1-D array, got {} dimensions", buffer.dimensions()))));
    }
    Some(buffer.to_vec(obj.py()).map(|values| values.into_iter().map(Into::into).collect()))
}

fn buffer_as_wide<T: Element + Copy>(obj: &Bound<'_, PyAny>, to_float: fn(T) -> f64) -> Option<PyResult<Vec<f64>>> {
    let buffer = PyBuffer::<T>::get(obj).ok()?;
    if buffer.dimensions() != 1 {
        return Some(Err(PyTypeError::new_err(format!("expected a 1-D array, got {} dimensions", buffer.dimensions()))));
    }
    Some(buffer.to_vec(obj.py()).map(|values| values.into_iter().map(to_float).collect()))
}

fn buffer_floats(obj: &Bound<'_, PyAny>) -> Option<PyResult<Vec<f64>>> {
    buffer_as::<f64>(obj)
        .or_else(|| buffer_as::<f32>(obj))
        .or_else(|| buffer_as_wide::<i64>(obj, |v| v as f64))
        .or_else(|| buffer_as::<i32>(obj))
        .or_else(|| buffer_as::<i16>(obj))
        .or_else(|| buffer_as::<i8>(obj))
        .or_else(|| buffer_as_wide::<u64>(obj, |v| v as f64))
        .or_else(|| buffer_as::<u32>(obj))
        .or_else(|| buffer_as::<u16>(obj))
        .or_else(|| buffer_as::<u8>(obj))
}

fn unsupported(obj: &Bound<'_, PyAny>) -> PyErr {
    let name = obj.get_type().name().map(|n| n.to_string()).unwrap_or_else(|_| "?".into());
    PyTypeError::new_err(format!("unsupported: {name} implements neither the Arrow PyCapsule Interface nor the buffer protocol"))
}

// ---- Python functions -------------------------------------------------------------------

/// Float values of a numeric column (int, uint, float, decimal, bool); nulls become NaN.
/// Reads Arrow sources (`__arrow_c_array__` / `__arrow_c_stream__`) or 1-D buffers (numpy).
#[pyfunction]
pub fn arrow_column_f64(obj: &Bound<'_, PyAny>) -> PyResult<Vec<f64>> {
    if let Some(column) = import_arrow(obj)? {
        return floats_of(&single_column(column)?);
    }
    buffer_floats(obj).unwrap_or_else(|| Err(unsupported(obj)))
}

/// Text values of a column (any type castable to text); nulls become `None`.
#[pyfunction]
pub fn arrow_column_str(obj: &Bound<'_, PyAny>) -> PyResult<Vec<Option<String>>> {
    match import_arrow(obj)? {
        Some(column) => strings_of(&single_column(column)?),
        None => Err(unsupported(obj)),
    }
}

/// Whether `obj` can be read through the Arrow PyCapsule Interface.
#[pyfunction]
pub fn arrow_supported(obj: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(obj.hasattr("__arrow_c_array__")? || obj.hasattr("__arrow_c_stream__")?)
}

/// Columns of a table (polars/pandas DataFrame, pyarrow Table, duckdb relation) as
/// `[(name, kind, values)]`: kind "float" (numeric, nulls → NaN) or "str" (nulls → None).
#[pyfunction]
pub fn arrow_table_columns(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<Vec<(String, &'static str, Py<PyAny>)>> {
    let Some(table) = import_arrow(obj)? else { return Err(unsupported(obj)) };
    let DataType::Struct(fields) = table.field.data_type() else {
        return Err(PyTypeError::new_err(format!("expected a table, got a column of type {}", table.field.data_type())));
    };
    let mut out = Vec::with_capacity(fields.len());
    for (i, field) in fields.iter().enumerate() {
        let chunks: Vec<ArrayRef> = table.chunks.iter().map(|c| Arc::clone(c.as_struct().column(i))).collect();
        let column = ArrowColumn { field: field.as_ref().clone(), chunks };
        let (kind, values) = if is_numeric(field.data_type()) {
            ("float", floats_of(&column)?.into_pyobject(py)?.into_any().unbind())
        } else {
            ("str", strings_of(&column)?.into_pyobject(py)?.into_any().unbind())
        };
        out.push((field.name().clone(), kind, values));
    }
    Ok(out)
}
