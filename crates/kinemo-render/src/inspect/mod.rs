//! Scene-graph introspection shared by `kinemo inspect` (Python bindings) and the
//! `kinemo dev` preview server: JSON snapshots of objects and pixel picking.

mod object_snapshot;
mod pick;
mod value_sources;

pub use object_snapshot::{object_json, scene_snapshot_json};
pub use pick::{pick_object, pick_object_in_layout};
pub use value_sources::{placement_source, prop_source};
