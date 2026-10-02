//! Conversion of Rust errors into Python exceptions.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::PyErr;

pub(crate) fn bad_json(what: &str, e: serde_json::Error) -> PyErr {
    PyValueError::new_err(format!("invalid IR {what}: {e}"))
}

pub(crate) fn runtime(e: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

pub(crate) fn parse<T: serde::de::DeserializeOwned>(what: &str, json: &str) -> Result<T, PyErr> {
    serde_json::from_str(json).map_err(|e| bad_json(what, e))
}

pub(crate) fn to_json<T: serde::Serialize>(v: &T) -> String {
    serde_json::to_string(v).expect("IR values serialize")
}
