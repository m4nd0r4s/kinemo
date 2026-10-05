//! Pick and inspect requests: the object under a pixel of the draft frame (or a known
//! object), with its props; and the selection box that rides along with frames.

use serde_json::{json, Value as Json};

use kinemo_eval::Evaluator;
use kinemo_layout::Layout;
use kinemo_render::inspect::{object_json, pick_object_in_layout};
use kinemo_render::FrameSize;

use crate::preview_state::ScenePublication;

/// Snapshot of the topmost object under (`x`, `y`) at `t`, labelled from the scene meta,
/// or `null` when the pixel hits only background.
pub fn picked_object_json(publication: &ScenePublication, x: f64, y: f64, t: f64) -> Json {
    let scene = &publication.scene;
    let t = t.clamp(0.0, scene.duration.max(0.0));
    let opts = &publication.render_options;
    let size = FrameSize { width: opts.width, height: opts.height };
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    match pick_object_in_layout(&layout, t, size, x, y) {
        Some(id) => snapshot(publication, &layout, id, t),
        None => Json::Null,
    }
}

/// Snapshot of object `id` at `t`, or `null` for an id the scene does not have (the
/// selection can outlive a rebuild that removed its object).
pub fn inspected_object_json(publication: &ScenePublication, id: u32, t: f64) -> Json {
    let scene = &publication.scene;
    if id as usize >= scene.objects.len() {
        return Json::Null;
    }
    let t = t.clamp(0.0, scene.duration.max(0.0));
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    snapshot(publication, &layout, id, t)
}

/// `[{"id","pixel_bbox"}]` of the selected objects present at `t` (unknown ids and absent
/// objects are left out).
pub fn selection_json(publication: &ScenePublication, ids: &[u32], t: f64) -> Json {
    let scene = &publication.scene;
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    let boxes = ids
        .iter()
        .filter(|&&id| (id as usize) < scene.objects.len() && scene.present(id, t))
        .map(|&id| json!({"id": id, "pixel_bbox": pixel_bbox(publication, &layout, id, t)}))
        .collect();
    Json::Array(boxes)
}

fn pixel_bbox(publication: &ScenePublication, layout: &Layout, id: u32, t: f64) -> Json {
    let opts = &publication.render_options;
    let size = FrameSize { width: opts.width, height: opts.height };
    let pixels = size.pixel_affine(&publication.scene).transform_rect_bbox(layout.world_bbox(id, t));
    json!([pixels.x0, pixels.y0, pixels.x1, pixels.y1])
}

/// Values of `(object, prop)` items at `times`, one row per item (`null` where the object or
/// the prop is unknown); the scene is evaluated once per instant.
pub fn sampled_values_json(publication: &ScenePublication, items: &[(u32, String)], times: &[f64]) -> Json {
    let scene = &publication.scene;
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    let mut rows: Vec<Vec<Json>> = vec![Vec::with_capacity(times.len()); items.len()];
    for &t in times {
        let t = t.clamp(0.0, scene.duration.max(0.0));
        let mut objects: std::collections::HashMap<u32, Json> = std::collections::HashMap::new();
        for (row, (id, prop)) in rows.iter_mut().zip(items) {
            if *id as usize >= scene.objects.len() {
                row.push(Json::Null);
                continue;
            }
            let object = objects.entry(*id).or_insert_with(|| object_json(&layout, *id, t));
            row.push(object["props"].get(prop).cloned().unwrap_or(Json::Null));
        }
    }
    json!(rows)
}

fn snapshot(publication: &ScenePublication, layout: &Layout, id: u32, t: f64) -> Json {
    let mut object = object_json(layout, id, t);
    object["label"] = json!(publication.object_label(id));
    object["pixel_bbox"] = pixel_bbox(publication, layout, id, t);
    object["present"] = json!(publication.scene.present(id, t));
    object["ancestors"] = ancestors_json(publication, id);
    object
}

/// Chain of parents (nearest first) as `{id, kind, label}`, so the UI can show grouping.
fn ancestors_json(publication: &ScenePublication, id: u32) -> Json {
    let scene = &publication.scene;
    let mut out = vec![];
    let mut cur = scene.object(id).parent;
    while let Some(p) = cur {
        let obj = scene.object(p);
        out.push(json!({"id": p, "kind": obj.kind, "label": publication.object_label(p), "span": obj.span}));
        cur = obj.parent;
    }
    Json::Array(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::preview_state::PreviewState;
    use kinemo_ir::{Object, Scene, SceneConfig};

    fn scene_with_late_object() -> Scene {
        let mut scene = Scene::new(SceneConfig { width: 160, height: 90, ..SceneConfig::default() });
        scene.duration = 2.0;
        scene.objects.push(Object { id: 0, kind: "circle".into(), presence: vec![(1.0, true)], ..Default::default() });
        scene.roots.push(0);
        scene
    }

    #[test]
    fn selection_follows_presence_and_unknown_ids() {
        let state = PreviewState::new();
        state.set_scene(scene_with_late_object(), json!({}));
        let publication = state.current().unwrap();
        assert_eq!(selection_json(&publication, &[0], 0.5), json!([]));
        assert_eq!(selection_json(&publication, &[0], 1.5)[0]["pixel_bbox"].as_array().unwrap().len(), 4);
        assert_eq!(selection_json(&publication, &[7, 0], 1.5).as_array().unwrap().len(), 1);
        assert!(inspected_object_json(&publication, 7, 1.5).is_null());
        assert_eq!(inspected_object_json(&publication, 0, 0.5)["present"], false);
    }

    #[test]
    fn samples_have_one_row_per_item_and_null_for_unknown_ones() {
        let state = PreviewState::new();
        state.set_scene(scene_with_late_object(), json!({}));
        let publication = state.current().unwrap();
        let rows = sampled_values_json(&publication, &[(0, "opacity".into()), (9, "x".into()), (0, "nope".into())], &[0.0, 1.5]);
        assert_eq!(rows.as_array().unwrap().len(), 3);
        assert_eq!(rows[0].as_array().unwrap().len(), 2);
        assert!(rows[1][0].is_null() && rows[2][1].is_null());
    }
}
