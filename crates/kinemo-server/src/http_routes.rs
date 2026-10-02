//! HTTP routes: the embedded single-page UI (HTML, CSS, JavaScript modules) and the
//! WebSocket endpoint.

use std::sync::Arc;

use axum::extract::{Path, State, WebSocketUpgrade};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::Router;

use crate::preview_state::PreviewState;
use crate::websocket::run_session;

const INDEX_HTML: &str = include_str!("../ui/index.html");
const STYLE_CSS: &str = include_str!("../ui/style.css");

/// The page's JavaScript modules, served under `/ui/`.
const SCRIPTS: &[(&str, &str)] = &[
    ("main.js", include_str!("../ui/main.js")),
    ("state.js", include_str!("../ui/state.js")),
    ("connection.js", include_str!("../ui/connection.js")),
    ("frames.js", include_str!("../ui/frames.js")),
    ("playback.js", include_str!("../ui/playback.js")),
    ("selection.js", include_str!("../ui/selection.js")),
    ("editing.js", include_str!("../ui/editing.js")),
    ("widgets.js", include_str!("../ui/widgets.js")),
    ("colorpicker.js", include_str!("../ui/colorpicker.js")),
    ("canvas.js", include_str!("../ui/canvas.js")),
    ("inspector.js", include_str!("../ui/inspector.js")),
    ("timeline.js", include_str!("../ui/timeline.js")),
    ("outliner.js", include_str!("../ui/outliner.js")),
    ("problems.js", include_str!("../ui/problems.js")),
];

fn asset(content_type: &'static str, body: &'static str) -> Response {
    ([(header::CONTENT_TYPE, content_type), (header::CACHE_CONTROL, "no-cache")], body).into_response()
}

async fn script(Path(file): Path<String>) -> Response {
    match SCRIPTS.iter().find(|(name, _)| *name == file) {
        Some((_, body)) => asset("text/javascript; charset=utf-8", body),
        None => StatusCode::NOT_FOUND.into_response(),
    }
}

pub fn router(state: Arc<PreviewState>) -> Router {
    Router::new()
        .route("/", get(|| async { asset("text/html; charset=utf-8", INDEX_HTML) }))
        .route("/style.css", get(|| async { asset("text/css; charset=utf-8", STYLE_CSS) }))
        .route("/ui/{file}", get(script))
        .route("/ws", get(upgrade))
        .with_state(state)
}

async fn upgrade(ws: WebSocketUpgrade, State(state): State<Arc<PreviewState>>) -> Response {
    ws.on_upgrade(move |socket| run_session(socket, state))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_ui_module_is_served() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("ui");
        for entry in std::fs::read_dir(dir).unwrap() {
            let name = entry.unwrap().file_name().into_string().unwrap();
            if name.ends_with(".js") {
                assert!(SCRIPTS.iter().any(|(served, _)| *served == name), "ui/{name} is not in SCRIPTS");
            }
        }
    }
}
