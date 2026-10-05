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
    ("audio.js", include_str!("../ui/audio.js")),
    ("tracks.js", include_str!("../ui/tracks.js")),
    ("clip_inspector.js", include_str!("../ui/clip_inspector.js")),
    ("resizer.js", include_str!("../ui/resizer.js")),
    ("code_view.js", include_str!("../ui/code_view.js")),
    ("breakpoints.js", include_str!("../ui/breakpoints.js")),
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
        .route("/audio/{version}/{index}", get(audio))
        .route("/ws", get(upgrade))
        .with_state(state)
}

/// An audio clip of the current scene (only clips the scene uses are served).
async fn audio(Path((version, index)): Path<(u64, usize)>, State(state): State<Arc<PreviewState>>) -> Response {
    let Some(publication) = state.current() else { return StatusCode::NOT_FOUND.into_response() };
    if publication.version != version {
        return StatusCode::NOT_FOUND.into_response();
    }
    let Some(clip) = publication.scene.audio.get(index) else { return StatusCode::NOT_FOUND.into_response() };
    match std::fs::read(&clip.path) {
        Ok(bytes) => ([(header::CONTENT_TYPE, audio_type(&clip.path)), (header::CACHE_CONTROL, "max-age=3600")], bytes).into_response(),
        Err(_) => StatusCode::NOT_FOUND.into_response(),
    }
}

fn audio_type(path: &str) -> &'static str {
    match std::path::Path::new(path).extension().and_then(|e| e.to_str()).map(str::to_ascii_lowercase).as_deref() {
        Some("mp3") => "audio/mpeg",
        Some("ogg") => "audio/ogg",
        Some("flac") => "audio/flac",
        Some("m4a") => "audio/mp4",
        Some("aac") => "audio/aac",
        _ => "audio/wav",
    }
}

async fn upgrade(ws: WebSocketUpgrade, State(state): State<Arc<PreviewState>>) -> Response {
    ws.on_upgrade(move |socket| run_session(socket, state))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn audio_files_get_their_media_type() {
        assert_eq!(audio_type("voice/B03.wav"), "audio/wav");
        assert_eq!(audio_type("music.MP3"), "audio/mpeg");
        assert_eq!(audio_type("line.m4a"), "audio/mp4");
    }

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
