//! Where a value came from: placement (container, constraint, free) and prop timelines.

use serde_json::{json, Value as Json};

use kinemo_ir::{Entry, ObjectId, SignalId, Src};
use kinemo_layout::Layout;

/// Origin of an object's position at `t`: `container`, `place` or `free`.
pub fn placement_source(layout: &Layout, object: ObjectId, t: f64) -> Json {
    let obj = layout.scene().object(object);
    if let Some(parent) = obj.parent {
        if matches!(layout.scene().object(parent).kind.as_str(), "row" | "column" | "grid" | "stack") {
            return json!({"kind": "container", "container": parent});
        }
    }
    match obj.place.iter().rev().find(|e| e.t <= t) {
        Some(entry) => match &entry.p {
            Some(p) => json!({"kind": "place", "placement": p, "span": entry.span}),
            None => json!({"kind": "free", "span": entry.span}),
        },
        None => json!({"kind": "free"}),
    }
}

/// Origin of a signal's value at `t`, from the last timeline entry that started by then.
///
/// Kinds: `default` (not written by the user; no span), `initial` (construction argument),
/// `set`, `animation` (running or finished), `binding` (a live expression). Each but
/// `default` carries the source `span`.
pub fn prop_source(layout: &Layout, signal: SignalId, t: f64) -> Json {
    let sig = &layout.scene().signals[signal as usize];
    let last = sig.timeline.iter().rev().find(|e| e.start() <= t);
    match last {
        None if sig.span.file.is_empty() => json!({"kind": "default"}),
        None => json!({"kind": "initial", "span": sig.span}),
        Some(Entry::Set { src, span, t: at }) => {
            let kind = if matches!(src, Src::Expr { .. }) { "binding" } else { "set" };
            json!({"kind": kind, "t": at, "span": span})
        }
        Some(Entry::Anim { t0, t1, to, span, .. }) => {
            let running = t < *t1;
            let kind = if !running && matches!(to, Src::Expr { .. }) { "binding" } else { "animation" };
            json!({"kind": kind, "t0": t0, "t1": t1, "running": running, "span": span})
        }
    }
}
