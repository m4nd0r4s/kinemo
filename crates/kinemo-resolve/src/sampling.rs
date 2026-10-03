//! Timeline sampling: which instants to look at, and what the viewer sees at each one.
//!
//! Sample times are a uniform grid (default step 0.1 s) plus every timeline boundary
//! (set, animation start/end, presence toggle, placement change), so short events are
//! never skipped. At each instant, [`sample_frame`] lists the present leaves with their
//! world box, effective opacity and whether they are "at rest" (see [`MotionIndex`]).

use std::collections::HashMap;

use kurbo::Rect;

use kinemo_ir::{Entry, ObjectId, Scene, SignalId, Src, Value};
use kinemo_layout::Layout;

/// Default sampling step, in seconds.
pub const DEFAULT_SAMPLE_STEP: f64 = 0.1;

/// Two sample times closer than this are the same instant.
const SAME_INSTANT: f64 = 1e-9;

/// Sorted, deduplicated sample instants in `[0, scene.duration]`.
pub fn sample_times(scene: &Scene, step: f64) -> Vec<f64> {
    let step = if step.is_finite() && step > 0.0 { step } else { DEFAULT_SAMPLE_STEP };
    let duration = scene.duration.max(0.0);
    let grid_count = (duration / step).floor() as usize;
    // Grid instants are rounded to the nanosecond so reported times read cleanly (0.6, not 0.6000000000000001).
    let mut times: Vec<f64> = (0..=grid_count).map(|i| (i as f64 * step * 1e9).round() / 1e9).collect();
    times.push(duration);
    times.extend(timeline_boundaries(scene));
    times.retain(|t| t.is_finite() && *t >= 0.0 && *t <= duration + SAME_INSTANT);
    times.sort_by(f64::total_cmp);
    times.dedup_by(|a, b| (*a - *b).abs() < SAME_INSTANT);
    times
}

/// Every instant where something in the timeline starts or stops changing.
pub fn timeline_boundaries(scene: &Scene) -> Vec<f64> {
    let mut out = Vec::new();
    for signal in &scene.signals {
        for entry in &signal.timeline {
            out.push(entry.start());
            out.push(entry.end());
        }
    }
    for object in &scene.objects {
        out.extend(object.presence.iter().map(|(t, _)| *t));
        for entry in &object.place {
            out.push(entry.t);
            out.push(entry.t + entry.dur);
        }
    }
    out
}

/// Time intervals during which each object's own props (or placement) are animating.
///
/// An object is *at rest* at `t` when neither it nor any ancestor has an animation in
/// progress at `t` (the end instant of an animation counts as at rest). Motion
/// driven by expressions (`place(above=dot)` with an animated `dot`, `k.time`) does not
/// make an object "moving": those positions are what the viewer sees for as long as
/// the binding lasts, so lints judge them.
#[derive(Debug, Default)]
pub struct MotionIndex {
    intervals: HashMap<ObjectId, Vec<(f64, f64)>>,
}

impl MotionIndex {
    pub fn new(scene: &Scene) -> Self {
        let mut intervals: HashMap<ObjectId, Vec<(f64, f64)>> = HashMap::new();
        for signal in &scene.signals {
            let Some((owner, _)) = &signal.owner else { continue };
            for entry in &signal.timeline {
                if let Entry::Anim { t0, t1, .. } = entry {
                    if t1 > t0 {
                        intervals.entry(*owner).or_default().push((*t0, *t1));
                    }
                }
            }
        }
        for object in &scene.objects {
            for entry in object.place.iter().filter(|e| e.dur > 0.0) {
                intervals.entry(object.id).or_default().push((entry.t, entry.t + entry.dur));
            }
        }
        MotionIndex { intervals }
    }

    /// Whether `object` itself has an animation in progress at `t` (`t0 <= t < t1`: the
    /// start pose of an entrance is transient, the end pose is where the object rests).
    pub fn is_animating(&self, object: ObjectId, t: f64) -> bool {
        self.intervals
            .get(&object)
            .is_some_and(|spans| spans.iter().any(|(t0, t1)| *t0 - SAME_INSTANT <= t && t < *t1 - SAME_INSTANT))
    }

    /// Whether `object` and all its ancestors are at rest at `t`.
    pub fn is_at_rest(&self, scene: &Scene, object: ObjectId, t: f64) -> bool {
        ancestry(scene, object).all(|o| !self.is_animating(o, t))
    }
}

/// `object`, then its parent, grandparent, ... up to the root.
pub fn ancestry(scene: &Scene, object: ObjectId) -> impl Iterator<Item = ObjectId> + '_ {
    std::iter::successors(Some(object), move |&o| scene.object(o).parent)
}

/// Display name of an object: its name, else `kind#id`.
pub fn object_label(scene: &Scene, object: ObjectId) -> String {
    let o = scene.object(object);
    o.name.clone().unwrap_or_else(|| format!("{}#{}", o.kind, o.id))
}

/// What the viewer gets from one present leaf at one instant.
#[derive(Clone, Debug)]
pub struct LeafSample {
    pub id: ObjectId,
    pub is_text: bool,
    /// Object holding the text props (`text`, `size`): the leaf itself, or the text a
    /// glyph run belongs to.
    pub text_owner: ObjectId,
    /// World bounding box (layout position; render-only entry effects excluded).
    pub world_bbox: Rect,
    /// Opacity accumulated down the tree (`opacity` × verb fade), in `[0, 1]`.
    pub opacity: f64,
    /// `visible` is true for the leaf and all its ancestors.
    pub shown: bool,
    /// Draw/write progress is above zero (something of the leaf is painted).
    pub revealed: bool,
    /// See [`MotionIndex::is_at_rest`].
    pub at_rest: bool,
}

impl LeafSample {
    /// Painted with at least `min_opacity`.
    pub fn is_visible(&self, min_opacity: f64) -> bool {
        self.shown && self.revealed && self.opacity > min_opacity
    }
}

/// The scene at one sample instant.
#[derive(Clone, Debug)]
pub struct FrameSample {
    pub t: f64,
    /// Present leaves in tree order.
    pub leaves: Vec<LeafSample>,
    /// Values of the signals that are driven by expressions (see [`expression_signals`]).
    pub reactive_values: Vec<(SignalId, Value)>,
}

/// Signals whose timeline contains an expression source (live bindings): their value can
/// change without any animation entry being active.
pub fn expression_signals(scene: &Scene) -> Vec<SignalId> {
    let is_expr = |src: &Src| matches!(src, Src::Expr { .. });
    scene
        .signals
        .iter()
        .filter(|s| {
            s.timeline.iter().any(|e| match e {
                Entry::Set { src, .. } => is_expr(src),
                Entry::Anim { to, from, .. } => is_expr(to) || from.as_ref().is_some_and(is_expr),
            })
        })
        .map(|s| s.id)
        .collect()
}

/// Samples the scene at `t` through `layout`.
pub fn sample_frame(layout: &Layout, motion: &MotionIndex, reactive: &[SignalId], t: f64) -> FrameSample {
    let scene = layout.scene();
    let leaves = present_leaves(layout, t)
        .into_iter()
        .map(|(id, shown)| LeafSample {
            id,
            is_text: is_text_leaf(layout, id, t),
            text_owner: text_owner(layout, id, t),
            world_bbox: layout.world_bbox(id, t),
            opacity: accumulated_opacity(layout, id, t),
            shown,
            revealed: layout.prop_f(id, "_draw", t, 1.0).min(layout.prop_f(id, "_write", t, 1.0)) > 0.0,
            at_rest: motion.is_at_rest(scene, id, t),
        })
        .collect();
    let reactive_values = reactive.iter().map(|&s| (s, layout.evaluator().signal(s, t, layout))).collect();
    FrameSample { t, leaves, reactive_values }
}

/// A text leaf, or the `rest` run of a text-like group (parts split off, and the runs
/// inside them, are not judged separately, so a styled word does not count as text over
/// its own text).
fn is_text_leaf(layout: &Layout, id: ObjectId, t: f64) -> bool {
    let scene = layout.scene();
    match scene.object(id).kind.as_str() {
        "text" => true,
        "glyphs" => {
            let in_part = scene.object(id).parent.is_some_and(|p| scene.object(p).kind == "glyphs");
            layout.prop_bool(id, "rest", t, false) && !in_part
        }
        _ => false,
    }
}

fn text_owner(layout: &Layout, id: ObjectId, t: f64) -> ObjectId {
    let scene = layout.scene();
    if scene.object(id).kind != "glyphs" {
        return id;
    }
    if let Some(kinemo_ir::Value::Object(source)) = layout.prop(id, "source", t) {
        return source;
    }
    // Parts nest: the owner is the first ancestor that is not a part.
    let mut current = scene.object(id).parent;
    while let Some(parent) = current {
        if scene.object(parent).kind != "glyphs" {
            return parent;
        }
        current = scene.object(parent).parent;
    }
    id
}

/// Present leaves at `t` in tree order, with whether every ancestor is `visible`.
/// Mirrors the renderer's traversal, but keeps hidden leaves (flagged) so lints can
/// tell "hidden" from "absent".
fn present_leaves(layout: &Layout, t: f64) -> Vec<(ObjectId, bool)> {
    let scene = layout.scene();
    let mut out = Vec::new();
    let mut stack: Vec<(ObjectId, bool)> = scene.roots.iter().rev().map(|&r| (r, true)).collect();
    while let Some((o, parent_shown)) = stack.pop() {
        let shown = parent_shown && layout.prop_bool(o, "visible", t, true);
        if scene.object(o).children.is_some() {
            for child in layout.children(o, t).into_iter().rev() {
                stack.push((child, shown));
            }
        } else if scene.present(o, t) {
            out.push((o, shown));
        }
    }
    out
}

/// `opacity × _fade` multiplied from the leaf up to the root (the renderer's chain).
pub fn accumulated_opacity(layout: &Layout, leaf: ObjectId, t: f64) -> f64 {
    ancestry(layout.scene(), leaf)
        .map(|o| layout.prop_f(o, "opacity", t, 1.0) * layout.prop_f(o, "_fade", t, 1.0))
        .product::<f64>()
        .clamp(0.0, 1.0)
}

/// Approximate equality of runtime values (numbers within 1e-6).
pub fn values_close(a: &Value, b: &Value) -> bool {
    const TOLERANCE: f64 = 1e-6;
    let near = |x: f64, y: f64| (x - y).abs() <= TOLERANCE || (x.is_nan() && y.is_nan());
    match (a, b) {
        (Value::Float(_) | Value::Int(_), Value::Float(_) | Value::Int(_)) => near(a.as_f64(), b.as_f64()),
        (Value::Vec2(x), Value::Vec2(y)) => x.iter().zip(y).all(|(p, q)| near(*p, *q)),
        (Value::Color(x), Value::Color(y)) => x.iter().zip(y).all(|(p, q)| near(*p, *q)),
        (Value::List(x), Value::List(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| values_close(p, q)),
        _ => a == b,
    }
}
