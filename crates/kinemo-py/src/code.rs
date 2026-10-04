//! Language lookup for `k.Code`, so an unknown `lang=` is an error when the object is made.

use pyo3::prelude::*;

use kinemo_code::{supported_languages, Language};

/// Canonical name of a language name or alias (`"py"` -> `"python"`), or `None`.
#[pyfunction]
pub fn code_language(name: &str) -> Option<&'static str> {
    Language::from_name(name).map(Language::name)
}

/// Canonical names of every language `k.Code` highlights.
#[pyfunction]
pub fn code_languages() -> Vec<&'static str> {
    supported_languages()
}
