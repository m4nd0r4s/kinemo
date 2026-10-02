//! Debug overlays (`kinemo dev --debug layout,safe`): object boxes, constraint relations
//! and the safe area, in frame pixels.

use kurbo::{Point, Rect};
use serde_json::{json, Value as Json};

use kinemo_eval::Evaluator;
use kinemo_layout::Layout;
use kinemo_render::FrameSize;

use crate::preview_state::ScenePublication;

const SAFE_MARGIN: f64 = 0.5;

pub fn overlay_json(publication: &ScenePublication, t: f64) -> Json {
    let scene = &publication.scene;
    let opts = &publication.render_options;
    let size = FrameSize { width: opts.width, height: opts.height };
    let to_px = size.pixel_affine(scene);
    let px_rect = |r: Rect| {
        let a = to_px * Point::new(r.x0, r.y0);
        let b = to_px * Point::new(r.x1, r.y1);
        [a.x.min(b.x), a.y.min(b.y), a.x.max(b.x), a.y.max(b.y)]
    };
    let ev = Evaluator::new(scene);
    let layout = Layout::new(&ev);
    let mut boxes = Vec::new();
    let mut relations = Vec::new();
    for o in 0..scene.objects.len() as u32 {
        if !scene.present(o, t) {
            continue;
        }
        let object = scene.object(o);
        boxes.push(json!({
            "id": o,
            "label": publication.object_label(o),
            "kind": object.kind,
            "bbox": px_rect(layout.world_bbox(o, t)),
        }));
        if let Some(entry) = object.place.iter().rev().find(|e| e.t <= t) {
            if let Some(p) = &entry.p {
                if let Some(target) = p.target {
                    relations.push(json!({"from": o, "to": target, "side": p.side}));
                }
            }
        }
    }
    let (fw, fh) = (scene.config.frame_w, scene.config.frame_h);
    let safe = Rect::new(-fw / 2.0 + SAFE_MARGIN, -fh / 2.0 + SAFE_MARGIN, fw / 2.0 - SAFE_MARGIN, fh / 2.0 - SAFE_MARGIN);
    json!({"type": "overlay", "t": t, "boxes": boxes, "relations": relations, "safe": px_rect(safe)})
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::preview_state::PreviewState;
    use kinemo_ir::{Object, Scene, SceneConfig};

    #[test]
    fn overlay_lists_present_objects_and_safe_area() {
        let mut scene = Scene::new(SceneConfig { width: 160, height: 90, ..SceneConfig::default() });
        scene.duration = 1.0;
        scene.objects.push(Object { id: 0, kind: "circle".into(), presence: vec![(0.0, true)], ..Default::default() });
        scene.roots.push(0);
        let state = PreviewState::new();
        state.set_scene(scene, json!({}));
        let overlay = overlay_json(&state.current().unwrap(), 0.5);
        assert_eq!(overlay["boxes"].as_array().unwrap().len(), 1);
        assert_eq!(overlay["safe"].as_array().unwrap().len(), 4);
    }
}
