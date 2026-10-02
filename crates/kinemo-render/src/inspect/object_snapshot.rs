//! JSON snapshot of one object (and of the whole scene) at an instant.

use serde_json::{json, Map, Value as Json};

use kinemo_eval::Evaluator;
use kinemo_ir::{ObjectId, Scene};
use kinemo_layout::Layout;

use super::value_sources::{placement_source, prop_source};

/// Snapshot of `object` at `t`: kind, presence, position, bbox, evaluated props, the
/// source of each prop (`prop_sources`) and of the position, and the construction span.
pub fn object_json(layout: &Layout, object: ObjectId, t: f64) -> Json {
    let scene = layout.scene();
    let obj = scene.object(object);
    let bbox = layout.world_bbox(object, t);
    let mut props = Map::new();
    let mut prop_sources = Map::new();
    for (name, &signal) in obj.props.iter().filter(|(name, _)| !name.starts_with('_')) {
        let value = layout.evaluator().signal(signal, t, layout);
        props.insert(name.clone(), serde_json::to_value(value).unwrap_or(Json::Null));
        prop_sources.insert(name.clone(), prop_source(layout, signal, t));
    }
    json!({
        "id": object,
        "kind": obj.kind,
        "name": obj.name,
        "parent": obj.parent,
        "present": scene.present(object, t),
        "position": layout.translation(object, t),
        "bbox": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
        "props": props,
        "prop_sources": prop_sources,
        "position_source": placement_source(layout, object, t),
        "span": obj.span,
    })
}

/// Snapshots of every object in `scene` at `t`, in id order.
pub fn scene_snapshot_json(scene: &Scene, t: f64) -> Vec<Json> {
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    (0..scene.objects.len() as ObjectId).map(|o| object_json(&layout, o, t)).collect()
}
