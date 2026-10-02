//! Frame requests: cached draft-quality PNGs rendered in Rust (GPU with feature `gpu`).

use std::sync::Arc;

use serde_json::{json, Value as Json};

use kinemo_render::{raster, render_frame_with_backend};

use crate::frame_backend::preview_frame_backend;

use crate::frame_cache::{frame_index_for_time, FrameKey};
use crate::preview_state::{PreviewState, ScenePublication};

pub struct RenderedFrame {
    pub header: Json,
    pub png: Arc<Vec<u8>>,
}

/// PNG of the frame nearest to `t` (blocking: call from a blocking task).
pub fn frame_at(state: &PreviewState, publication: &ScenePublication, t: f64, request_id: Option<u64>) -> RenderedFrame {
    let opts = &publication.render_options;
    let frame_index = frame_index_for_time(t, opts.fps, publication.frame_count());
    let frame_time = frame_index as f64 / opts.fps;
    let segment_hash = kinemo_render::segments::segment_hash_at(&publication.segments, frame_time);
    let key = FrameKey { segment_hash, frame_index };
    let cached = state.frame_cache.lock().expect("cache lock").get(key);
    let png = cached.unwrap_or_else(|| {
        let image = render_frame_with_backend(preview_frame_backend(), &publication.scene, frame_time, opts);
        let png = Arc::new(raster::encode_png(&image));
        state.frame_cache.lock().expect("cache lock").insert(key, png.clone());
        png
    });
    let header = json!({
        "type": "frame",
        "id": request_id,
        "t": frame_time,
        "frame": frame_index,
        "version": publication.version,
        "width": opts.width,
        "height": opts.height,
    });
    RenderedFrame { header, png }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kinemo_ir::{Scene, SceneConfig};

    fn tiny_scene() -> Scene {
        let mut scene = Scene::new(SceneConfig { width: 64, height: 36, fps: 10.0, ..SceneConfig::default() });
        scene.duration = 1.0;
        scene
    }

    #[test]
    fn repeated_requests_hit_the_cache_and_snap_to_frames() {
        let state = PreviewState::new();
        state.set_scene(tiny_scene(), json!({}));
        let publication = state.current().unwrap();
        let first = frame_at(&state, &publication, 0.31, Some(1));
        let second = frame_at(&state, &publication, 0.29, Some(2));
        assert!(Arc::ptr_eq(&first.png, &second.png));
        assert_eq!(first.header["frame"], 3);
        assert_eq!(second.header["id"], 2);
        assert!((first.header["t"].as_f64().unwrap() - 0.3).abs() < 1e-9);
        assert_eq!(&first.png[1..4], b"PNG");
    }

    #[test]
    fn an_identical_rebuild_reuses_cached_frames() {
        let state = PreviewState::new();
        state.set_scene(tiny_scene(), json!({}));
        let old = frame_at(&state, &state.current().unwrap(), 0.0, None);
        assert_eq!(state.set_scene(tiny_scene(), json!({})), 2);
        let new = frame_at(&state, &state.current().unwrap(), 0.0, None);
        assert!(Arc::ptr_eq(&old.png, &new.png));
        assert_eq!(new.header["version"], 2);
    }

    #[test]
    fn a_changed_scene_invalidates_cached_frames() {
        let state = PreviewState::new();
        state.set_scene(tiny_scene(), json!({}));
        let old = frame_at(&state, &state.current().unwrap(), 0.0, None);
        let mut changed = tiny_scene();
        changed.config.background = [1.0, 0.0, 0.0, 1.0];
        state.set_scene(changed, json!({}));
        let new = frame_at(&state, &state.current().unwrap(), 0.0, None);
        assert!(!Arc::ptr_eq(&old.png, &new.png));
        assert_eq!(state.frame_cache.lock().unwrap().len(), 1);
    }

    #[test]
    fn a_failed_build_keeps_the_last_good_scene() {
        let state = PreviewState::new();
        state.set_scene(tiny_scene(), json!({"timeline": []}));
        state.set_error(json!([{"code": "K0001", "message": "boom"}]));
        assert_eq!(state.current().unwrap().version, 1);
        assert_eq!(state.last_error_message().unwrap()["type"], "error");
        state.set_scene(tiny_scene(), json!({}));
        assert!(state.last_error_message().is_none());
    }

    #[test]
    fn scene_meta_gains_render_settings() {
        let state = PreviewState::new();
        state.set_scene(tiny_scene(), json!({"scene": "x"}));
        let message = state.current().unwrap().scene_message();
        assert_eq!(message["type"], "scene");
        assert_eq!(message["meta"]["scene"], "x");
        assert_eq!(message["meta"]["render"]["frame_count"], 10);
        assert_eq!(message["meta"]["render"]["width"], 64);
    }
}
