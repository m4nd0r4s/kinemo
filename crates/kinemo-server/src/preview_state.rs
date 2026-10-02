//! Shared state of the preview: the current scene, its metadata, the last build error,
//! the frame cache and the channel that pushes updates to connected clients.

use std::sync::{Arc, Mutex, RwLock};

use serde_json::{json, Value as Json};
use tokio::sync::broadcast;

use kinemo_ir::Scene;
use kinemo_render::{Quality, RenderOptions};

use crate::frame_cache::FrameCache;
use crate::protocol;

/// Byte budget of the PNG frame cache.
const FRAME_CACHE_BYTES: usize = 512 * 1024 * 1024;

/// The scene being previewed, immutable once published.
pub struct ScenePublication {
    pub version: u64,
    pub scene: Arc<Scene>,
    pub render_options: RenderOptions,
    /// Timeline segments with content hashes (frame cache keys).
    pub segments: Vec<kinemo_render::segments::Segment>,
    /// Python-built metadata (timeline, marks, diagnostics, object labels) plus `render`.
    pub meta: Json,
}

impl ScenePublication {
    pub fn frame_count(&self) -> u64 {
        self.render_options.frame_count(self.scene.duration) as u64
    }

    /// Display label of an object, from `meta.objects[id].label`.
    pub fn object_label(&self, id: u32) -> Option<String> {
        self.meta["objects"][id.to_string()]["label"].as_str().map(str::to_owned)
    }

    /// Message announcing this scene to clients.
    pub fn scene_message(&self) -> Json {
        json!({"type": "scene", "version": self.version, "meta": self.meta})
    }
}

pub struct PreviewState {
    current: RwLock<Option<Arc<ScenePublication>>>,
    last_error: RwLock<Option<Json>>,
    pub frame_cache: Mutex<FrameCache>,
    updates: broadcast::Sender<Arc<Json>>,
    /// Source edits from the page, waiting for the Python side.
    edits: Mutex<Vec<Json>>,
}

impl Default for PreviewState {
    fn default() -> Self {
        Self::new()
    }
}

impl PreviewState {
    pub fn new() -> Self {
        let (updates, _) = broadcast::channel(16);
        PreviewState {
            current: RwLock::new(None),
            last_error: RwLock::new(None),
            frame_cache: Mutex::new(FrameCache::new(FRAME_CACHE_BYTES)),
            updates,
            edits: Mutex::new(Vec::new()),
        }
    }

    pub fn current(&self) -> Option<Arc<ScenePublication>> {
        self.current.read().expect("scene lock").clone()
    }

    pub fn last_error_message(&self) -> Option<Json> {
        self.last_error.read().expect("error lock").as_ref().map(protocol::error_message)
    }

    pub fn subscribe(&self) -> broadcast::Receiver<Arc<Json>> {
        self.updates.subscribe()
    }

    /// Publishes a new scene (draft quality), clears the build error and notifies clients.
    pub fn set_scene(&self, scene: Scene, mut meta: Json) -> u64 {
        let render_options = RenderOptions::for_scene(&scene, Quality::Draft);
        if !meta.is_object() {
            meta = json!({});
        }
        meta["render"] = json!({
            "width": render_options.width,
            "height": render_options.height,
            "fps": render_options.fps,
            "frame_count": render_options.frame_count(scene.duration),
            "frame_w": scene.config.frame_w,
            "frame_h": scene.config.frame_h,
        });
        meta["duration"] = json!(scene.duration);
        let publication = {
            let mut current = self.current.write().expect("scene lock");
            let version = current.as_ref().map_or(1, |p| p.version + 1);
            let segments = kinemo_render::segments::segments(&scene);
            let publication = Arc::new(ScenePublication { version, scene: Arc::new(scene), render_options, segments, meta });
            *current = Some(publication.clone());
            publication
        };
        *self.last_error.write().expect("error lock") = None;
        let live = publication.segments.iter().map(|s| s.hash).collect();
        self.frame_cache.lock().expect("cache lock").retain_segments(&live);
        let _ = self.updates.send(Arc::new(publication.scene_message()));
        publication.version
    }

    /// Queues a source edit from the page.
    pub fn queue_edit(&self, edit: Json) {
        self.edits.lock().expect("edits lock").push(edit);
    }

    /// Takes the queued edits, oldest first.
    pub fn take_edits(&self) -> Vec<Json> {
        std::mem::take(&mut *self.edits.lock().expect("edits lock"))
    }

    /// Pushes a message to every connected page (edit results).
    pub fn notify(&self, message: Json) {
        let _ = self.updates.send(Arc::new(message));
    }

    /// Records a failed build; the last good scene stays published.
    pub fn set_error(&self, diagnostics: Json) {
        let message = protocol::error_message(&diagnostics);
        *self.last_error.write().expect("error lock") = Some(diagnostics);
        let _ = self.updates.send(Arc::new(message));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn edits_are_taken_once_in_order() {
        let state = PreviewState::new();
        state.queue_edit(json!({"id": 1}));
        state.queue_edit(json!({"id": 2}));
        assert_eq!(state.take_edits(), vec![json!({"id": 1}), json!({"id": 2})]);
        assert!(state.take_edits().is_empty());
    }

    #[test]
    fn notifications_reach_subscribers() {
        let state = PreviewState::new();
        let mut updates = state.subscribe();
        state.notify(json!({"type": "edit_result", "ok": true}));
        assert_eq!(updates.try_recv().unwrap()["type"], "edit_result");
    }
}
