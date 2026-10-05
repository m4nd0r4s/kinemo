//! WebSocket protocol between the preview page and the server.
//!
//! All control messages are JSON text frames with a `type` field.
//!
//! Client → server:
//! - `{"type":"frame","t":1.25,"id":7,"select":[3,4],"overlay":true}`: render the frame
//!   nearest to `t`. `id` is optional and echoed back; `select` (object ids) adds those
//!   objects' boxes at the frame's time, and `overlay` the debug overlay, to the header, so
//!   both stay in step with the image during playback.
//! - `{"type":"pick","x":412,"y":230,"t":1.25,"id":8}`: topmost object under the pixel
//!   (`x`, `y`) of the rendered frame (frame pixels, y-down, origin top-left).
//! - `{"type":"inspect","object":3,"t":1.25,"id":9}`: snapshot of a known object (the
//!   selection, as it moves); answered like `pick`.
//! - `{"type":"sample","id":11,"items":[{"object":3,"prop":"x"}],"times":[0,0.5,1]}`: the
//!   values of props at several instants in one call (the Watch list and its sparklines);
//!   at most 12 items and 240 instants.
//! - `{"type":"open","file":"/abs/scene.py","line":12}`: open a source line in the editor of
//!   `[editor] command`, when it is a command the page cannot open by URL. Queued for the
//!   Python side like an edit.
//! - `{"type":"edit","id":10,"live":false,"changes":[{"site":"<span key>","target":"r","value":"0.5"}]}`:
//!   change the scene's source. Queued for the Python side (`take_edits`), which answers
//!   with an `edit_result` push; `live` edits rebuild from the edited text without writing
//!   the file (dragging a value).
//!
//! Server → client:
//! - Frame: one **binary** message = `u32` big-endian header length `n`, then `n` bytes
//!   of UTF-8 JSON header `{"type":"frame","id","t","frame","version","width","height"}`
//!   (`t` = exact time of the rendered frame), then the PNG bytes. With `select`, the
//!   header has `selection`: `[{"id","pixel_bbox"}]` for the selected objects present at
//!   that time; with `overlay`, it has `overlay`: `{"boxes","relations","safe"}`.
//! - `{"type":"pick","id","t","x","y","object":{...}|null}`: the object snapshot
//!   (`id`, `kind`, `label`, `props`, `prop_sources`, `position_source`, `bbox`, `span`,
//!   and `drawn_glyphs` on the runs that draw a text);
//!   also the answer to `inspect` (without `x`, `y`).
//! - `{"type":"scene","version":n,"meta":{...}}`: sent on connect and whenever a new
//!   scene is published.
//! - `{"type":"error","diagnostics":[...]}`: the latest rebuild failed; the previous
//!   scene stays live.
//! - `{"type":"sample","id","values":[[v_t0, v_t1, ...], ...]}`: one row per item, `null`
//!   for an unknown object or prop.
//! - `{"type":"edit_result","id","ok","message"}`: outcome of an edit, pushed by Python.
//! - `{"type":"notice","message":"..."}`: request could not be served (no scene yet,
//!   malformed message).

use serde::Deserialize;
use serde_json::{json, Value as Json};

#[derive(Debug, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ClientMessage {
    Frame {
        t: f64,
        #[serde(default)]
        id: Option<u64>,
        /// Selected objects whose boxes ride along with the frame.
        #[serde(default)]
        select: Vec<u32>,
        /// Whether to include the debug overlay.
        #[serde(default)]
        overlay: bool,
    },
    Pick {
        x: f64,
        y: f64,
        t: f64,
        #[serde(default)]
        id: Option<u64>,
    },
    /// A source edit, forwarded as-is to the Python side.
    Edit {
        #[serde(default)]
        id: Option<u64>,
        #[serde(default)]
        live: bool,
        changes: Json,
    },
    /// Open a source line in the configured editor (run by the Python side).
    Open {
        file: String,
        #[serde(default)]
        line: u32,
    },
    /// Values of props at several instants (the Watch list).
    Sample {
        #[serde(default)]
        id: Option<u64>,
        items: Vec<SampleItem>,
        times: Vec<f64>,
    },
    /// Snapshot of a known object at `t`.
    Inspect {
        object: u32,
        t: f64,
        #[serde(default)]
        id: Option<u64>,
    },
}

#[derive(Debug, Deserialize, PartialEq)]
pub struct SampleItem {
    pub object: u32,
    pub prop: String,
}

/// Most items and instants one `sample` request evaluates.
pub const SAMPLE_ITEMS: usize = 12;
pub const SAMPLE_TIMES: usize = 240;

pub fn parse_client_message(text: &str) -> Result<ClientMessage, String> {
    serde_json::from_str(text).map_err(|e| format!("bad message: {e}"))
}

pub fn error_message(diagnostics: &Json) -> Json {
    json!({"type": "error", "diagnostics": diagnostics})
}

pub fn notice_message(message: &str) -> Json {
    json!({"type": "notice", "message": message})
}

/// Binary frame message: length-prefixed JSON header followed by the PNG.
pub fn frame_message(header: &Json, png: &[u8]) -> Vec<u8> {
    let header = serde_json::to_vec(header).expect("header serializes");
    let mut out = Vec::with_capacity(4 + header.len() + png.len());
    out.extend_from_slice(&(header.len() as u32).to_be_bytes());
    out.extend_from_slice(&header);
    out.extend_from_slice(png);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_frame_and_pick_requests() {
        assert_eq!(
            parse_client_message(r#"{"type":"frame","t":1.5}"#),
            Ok(ClientMessage::Frame { t: 1.5, id: None, select: vec![], overlay: false })
        );
        assert_eq!(
            parse_client_message(r#"{"type":"frame","t":1,"select":[4],"overlay":true}"#),
            Ok(ClientMessage::Frame { t: 1.0, id: None, select: vec![4], overlay: true })
        );
        assert_eq!(
            parse_client_message(r#"{"type":"inspect","object":2,"t":0.5}"#),
            Ok(ClientMessage::Inspect { object: 2, t: 0.5, id: None })
        );
        assert!(matches!(
            parse_client_message(r#"{"type":"edit","id":1,"changes":[{"site":"a","target":"r","value":"1"}]}"#),
            Ok(ClientMessage::Edit { id: Some(1), live: false, .. })
        ));
        assert_eq!(
            parse_client_message(r#"{"type":"pick","x":1,"y":2,"t":0,"id":3}"#),
            Ok(ClientMessage::Pick { x: 1.0, y: 2.0, t: 0.0, id: Some(3) })
        );
        assert_eq!(
            parse_client_message(r#"{"type":"open","file":"/a/s.py","line":3}"#),
            Ok(ClientMessage::Open { file: "/a/s.py".into(), line: 3 })
        );
        assert_eq!(
            parse_client_message(r#"{"type":"sample","id":4,"items":[{"object":1,"prop":"x"}],"times":[0,1]}"#),
            Ok(ClientMessage::Sample { id: Some(4), items: vec![SampleItem { object: 1, prop: "x".into() }], times: vec![0.0, 1.0] })
        );
        assert!(parse_client_message(r#"{"type":"nope"}"#).is_err());
    }

    #[test]
    fn frame_message_is_length_prefixed() {
        let msg = frame_message(&json!({"type": "frame"}), b"PNG");
        let n = u32::from_be_bytes(msg[..4].try_into().unwrap()) as usize;
        let header: Json = serde_json::from_slice(&msg[4..4 + n]).unwrap();
        assert_eq!(header["type"], "frame");
        assert_eq!(&msg[4 + n..], b"PNG");
    }
}
