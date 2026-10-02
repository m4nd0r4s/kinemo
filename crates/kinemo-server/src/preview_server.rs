//! Server lifecycle: binds the port, runs tokio on a background thread, stops on demand.

use std::net::{SocketAddr, TcpListener};
use std::sync::Arc;
use std::thread::JoinHandle;

use serde_json::Value as Json;
use tokio::sync::oneshot;

use kinemo_ir::Scene;

use crate::http_routes::router;
use crate::preview_state::PreviewState;

/// A running preview server. Dropping it stops the server.
pub struct PreviewServer {
    state: Arc<PreviewState>,
    address: SocketAddr,
    shutdown: Option<oneshot::Sender<()>>,
    thread: Option<JoinHandle<()>>,
}

impl PreviewServer {
    /// Binds `127.0.0.1:port` (0 = any free port) and starts serving in the background.
    pub fn start(port: u16) -> std::io::Result<Self> {
        let listener = TcpListener::bind(("127.0.0.1", port))?;
        listener.set_nonblocking(true)?;
        let address = listener.local_addr()?;
        let state = Arc::new(PreviewState::new());
        let (shutdown, stopped) = oneshot::channel::<()>();
        let app = router(state.clone());
        let runtime = tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_all().build()?;
        let thread = std::thread::Builder::new().name("kinemo-preview".into()).spawn(move || {
            runtime.block_on(async move {
                let listener = match tokio::net::TcpListener::from_std(listener) {
                    Ok(l) => l,
                    Err(e) => return eprintln!("kinemo dev: {e}"),
                };
                // Not a graceful shutdown: open WebSocket sessions would keep it waiting.
                tokio::select! {
                    result = axum::serve(listener, app) => {
                        if let Err(e) = result {
                            eprintln!("kinemo dev: server stopped: {e}");
                        }
                    }
                    _ = stopped => {}
                }
            });
            // Drops the remaining session tasks without waiting for them.
            runtime.shutdown_background();
        })?;
        Ok(PreviewServer { state, address, shutdown: Some(shutdown), thread: Some(thread) })
    }

    pub fn url(&self) -> String {
        format!("http://{}/", self.address)
    }

    pub fn port(&self) -> u16 {
        self.address.port()
    }

    /// Publishes a scene with its metadata; returns the new scene version.
    pub fn set_scene(&self, scene: Scene, meta: Json) -> u64 {
        self.state.set_scene(scene, meta)
    }

    /// Reports a failed rebuild (the last good scene keeps being served).
    pub fn set_error(&self, diagnostics: Json) {
        self.state.set_error(diagnostics)
    }

    /// Source edits sent by the page since the last call.
    pub fn take_edits(&self) -> Vec<Json> {
        self.state.take_edits()
    }

    /// Pushes a message (an edit result) to every connected page.
    pub fn notify(&self, message: Json) {
        self.state.notify(message)
    }

    pub fn state(&self) -> &Arc<PreviewState> {
        &self.state
    }

    /// Stops accepting connections and joins the server thread.
    pub fn stop(&mut self) {
        if let Some(shutdown) = self.shutdown.take() {
            let _ = shutdown.send(());
        }
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for PreviewServer {
    fn drop(&mut self) {
        self.stop();
    }
}
