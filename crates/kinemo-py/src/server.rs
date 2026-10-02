//! `PreviewServer`: the `kinemo dev` preview server, driven from Python.

use pyo3::prelude::*;

use crate::builder::Builder;
use crate::errors::{parse, runtime};

#[pyclass(module = "kinemo._core")]
pub struct PreviewServer {
    port: u16,
    running: Option<kinemo_server::PreviewServer>,
}

impl PreviewServer {
    fn running(&self) -> PyResult<&kinemo_server::PreviewServer> {
        self.running.as_ref().ok_or_else(|| runtime("preview server is not running"))
    }
}

#[pymethods]
impl PreviewServer {
    #[new]
    #[pyo3(signature = (port = 7878))]
    fn new(port: u16) -> Self {
        PreviewServer { port, running: None }
    }

    /// Binds the port, starts serving on a background thread and returns the URL.
    fn start(&mut self) -> PyResult<String> {
        if self.running.is_none() {
            let server = kinemo_server::PreviewServer::start(self.port)
                .map_err(|e| runtime(format!("cannot start preview server on port {}: {e}", self.port)))?;
            self.running = Some(server);
        }
        Ok(self.running()?.url())
    }

    #[getter]
    fn url(&self) -> PyResult<String> {
        Ok(self.running()?.url())
    }

    /// Publishes a copy of the builder's scene with its metadata JSON; returns the version.
    fn set_scene(&self, builder: PyRef<'_, Builder>, meta_json: &str) -> PyResult<u64> {
        let meta = parse("preview meta", meta_json)?;
        Ok(self.running()?.set_scene(builder.scene.clone(), meta))
    }

    /// Reports a failed rebuild; `diagnostics_json` is a JSON list of diagnostics.
    fn set_error(&self, diagnostics_json: &str) -> PyResult<()> {
        let diagnostics = parse("diagnostics", diagnostics_json)?;
        self.running()?.set_error(diagnostics);
        Ok(())
    }

    /// Source edits sent by the page since the last call, as JSON strings.
    fn take_edits(&self) -> PyResult<Vec<String>> {
        Ok(self.running()?.take_edits().iter().map(|e| e.to_string()).collect())
    }

    /// Pushes a JSON message (an edit result) to every connected page.
    fn notify(&self, message_json: &str) -> PyResult<()> {
        let message = parse("notification", message_json)?;
        self.running()?.notify(message);
        Ok(())
    }

    fn stop(&mut self, py: Python<'_>) {
        if let Some(mut server) = self.running.take() {
            py.detach(move || server.stop());
        }
    }
}
