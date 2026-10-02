//! WebSocket session: answers frame/pick/inspect requests and forwards scene/error pushes.

use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket};
use serde_json::Value as Json;
use tokio::sync::broadcast::error::RecvError;

use crate::frame_service::frame_at;
use crate::pick_service::{inspected_object_json, picked_object_json, selection_json};
use crate::preview_state::PreviewState;
use crate::overlay_service::overlay_json;
use crate::protocol::{frame_message, notice_message, parse_client_message, ClientMessage};

fn text(message: &Json) -> Message {
    Message::Text(message.to_string().into())
}

pub async fn run_session(mut socket: WebSocket, state: Arc<PreviewState>) {
    let mut updates = state.subscribe();
    if let Some(publication) = state.current() {
        if socket.send(text(&publication.scene_message())).await.is_err() {
            return;
        }
    }
    if let Some(error) = state.last_error_message() {
        if socket.send(text(&error)).await.is_err() {
            return;
        }
    }
    loop {
        tokio::select! {
            incoming = socket.recv() => {
                let Some(Ok(message)) = incoming else { return };
                let reply = match message {
                    Message::Text(body) => answer(&state, body.as_str()).await,
                    Message::Close(_) => return,
                    _ => continue,
                };
                if let Some(reply) = reply {
                    if socket.send(reply).await.is_err() {
                        return;
                    }
                }
            }
            update = updates.recv() => {
                match update {
                    Ok(message) => {
                        if socket.send(text(&message)).await.is_err() {
                            return;
                        }
                    }
                    Err(RecvError::Lagged(_)) => continue,
                    Err(RecvError::Closed) => return,
                }
            }
        }
    }
}

async fn answer(state: &Arc<PreviewState>, body: &str) -> Option<Message> {
    let request = match parse_client_message(body) {
        Ok(r) => r,
        Err(e) => return Some(text(&notice_message(&e))),
    };
    if let ClientMessage::Edit { id, live, changes } = request {
        // Answered later by the Python side, with an `edit_result` push.
        state.queue_edit(serde_json::json!({"id": id, "live": live, "changes": changes}));
        return None;
    }
    let Some(publication) = state.current() else {
        return Some(text(&notice_message("no scene yet")));
    };
    let state = state.clone();
    let work = tokio::task::spawn_blocking(move || match request {
        ClientMessage::Frame { t, id, select, overlay } => {
            let mut frame = frame_at(&state, &publication, t, id);
            let frame_time = frame.header["t"].as_f64().unwrap_or(t);
            if !select.is_empty() {
                frame.header["selection"] = selection_json(&publication, &select, frame_time);
            }
            if overlay {
                frame.header["overlay"] = overlay_json(&publication, frame_time);
            }
            Message::Binary(frame_message(&frame.header, &frame.png).into())
        }
        ClientMessage::Inspect { object, t, id } => {
            let snapshot = inspected_object_json(&publication, object, t);
            text(&serde_json::json!({"type": "pick", "id": id, "t": t, "object": snapshot}))
        }
        ClientMessage::Pick { x, y, t, id } => {
            let object = picked_object_json(&publication, x, y, t);
            text(&serde_json::json!({"type": "pick", "id": id, "t": t, "x": x, "y": y, "object": object}))
        }
        ClientMessage::Edit { .. } => unreachable!("edits are queued above"),
    });
    Some(work.await.unwrap_or_else(|e| text(&notice_message(&format!("render failed: {e}")))))
}
