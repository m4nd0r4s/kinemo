//! Python bindings: the only crate that knows about Python.
//!
//! The build phase pushes IR nodes into a [`builder::Builder`] incrementally; queries
//! (`.now`, layout reads, inspect) and outputs (frames, video) run on that IR.

mod arrow;
mod boolean;
mod builder;
mod errors;
mod inspect;
mod lints;
mod math;
mod media;
mod output;
mod server;

use pyo3::prelude::*;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("IR_VERSION", kinemo_ir::IR_VERSION)?;
    m.add_class::<builder::Builder>()?;
    m.add_class::<server::PreviewServer>()?;
    m.add_function(wrap_pyfunction!(output::ffmpeg_available, m)?)?;
    m.add_function(wrap_pyfunction!(output::measure_text, m)?)?;
    m.add_function(wrap_pyfunction!(output::render_movie, m)?)?;
    m.add_function(wrap_pyfunction!(arrow::arrow_column_f64, m)?)?;
    m.add_function(wrap_pyfunction!(arrow::arrow_column_str, m)?)?;
    m.add_function(wrap_pyfunction!(arrow::arrow_supported, m)?)?;
    m.add_function(wrap_pyfunction!(arrow::arrow_table_columns, m)?)?;
    Ok(())
}
