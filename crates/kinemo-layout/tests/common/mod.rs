//! Shared scene-building helpers for the layout integration tests.
//!
//! Scenes are built directly as IR values: every prop is a signal, objects are present
//! from t=0 unless told otherwise, and roots are computed from the parent links.
#![allow(dead_code)]

use kurbo::Rect;

use kinemo_eval::Evaluator;
use kinemo_ir::{
    Blend, Ease, Entry, Expr, Lerp, Object, ObjectId, PlaceEntry, Placement, Scene, SceneConfig, Side, Signal,
    SignalId, Span, Src, Value,
};
use kinemo_layout::Layout;

pub const EPSILON: f64 = 1e-9;

/// Fluent builder of IR scenes for tests.
pub struct SceneBuilder {
    scene: Scene,
}

impl Default for SceneBuilder {
    fn default() -> Self {
        Self::new()
    }
}

impl SceneBuilder {
    pub fn new() -> Self {
        SceneBuilder { scene: Scene::new(SceneConfig::default()) }
    }

    /// Adds a free signal and returns its id.
    pub fn signal(&mut self, initial: Value, lerp: Lerp) -> SignalId {
        let id = self.scene.signals.len() as SignalId;
        self.scene.signals.push(Signal { id, initial, lerp, timeline: vec![], owner: None, span: Span::default() });
        id
    }

    /// Appends a timeline entry to a signal.
    pub fn entry(&mut self, signal: SignalId, entry: Entry) -> &mut Self {
        self.scene.signals[signal as usize].timeline.push(entry);
        self
    }

    /// Adds an object of `kind`, present from t=0.
    pub fn object(&mut self, kind: &str) -> ObjectId {
        let id = self.scene.objects.len() as ObjectId;
        self.scene.objects.push(Object { id, kind: kind.into(), presence: vec![(0.0, true)], ..Default::default() });
        id
    }

    /// Sets a prop (as a new signal with `value` as its initial value).
    pub fn prop(&mut self, obj: ObjectId, name: &str, value: Value) -> SignalId {
        let lerp = if matches!(value, Value::Str(_) | Value::Bool(_)) { Lerp::StepEnd } else { Lerp::Linear };
        let id = self.signal(value, lerp);
        self.scene.signals[id as usize].owner = Some((obj, name.into()));
        self.scene.objects[obj as usize].props.insert(name.into(), id);
        id
    }

    pub fn prop_f(&mut self, obj: ObjectId, name: &str, value: f64) -> SignalId {
        self.prop(obj, name, Value::Float(value))
    }

    /// Chainable form of [`SceneBuilder::prop`].
    pub fn with(&mut self, obj: ObjectId, name: &str, value: Value) -> &mut Self {
        self.prop(obj, name, value);
        self
    }

    /// Signal id of an existing prop.
    pub fn prop_signal(&self, obj: ObjectId, name: &str) -> SignalId {
        self.scene.prop(obj, name).unwrap_or_else(|| panic!("object {obj} has no prop {name}"))
    }

    /// A `w` x `h` rectangle centered on its origin.
    pub fn rect(&mut self, w: f64, h: f64) -> ObjectId {
        let id = self.object("rect");
        self.prop_f(id, "w", w);
        self.prop_f(id, "h", h);
        id
    }

    pub fn presence(&mut self, obj: ObjectId, toggles: Vec<(f64, bool)>) -> &mut Self {
        self.scene.objects[obj as usize].presence = toggles;
        self
    }

    /// Pushes a placement timeline entry.
    pub fn place_entry(&mut self, obj: ObjectId, t: f64, dur: f64, ease: Ease, p: Option<Placement>) -> &mut Self {
        self.scene.objects[obj as usize].place.push(PlaceEntry { t, dur, ease, p, span: Default::default() });
        self
    }

    /// Placement active from t=0, without blending.
    pub fn place(&mut self, obj: ObjectId, p: Placement) -> &mut Self {
        self.place_entry(obj, 0.0, 0.0, Ease::Linear, Some(p))
    }

    /// Makes `parent` a group-like node holding `children` (children signal uses `Lerp::Layout`).
    pub fn children(&mut self, parent: ObjectId, children: &[ObjectId]) -> SignalId {
        let id = self.signal(object_list(children), Lerp::Layout);
        self.scene.signals[id as usize].owner = Some((parent, "children".into()));
        self.scene.objects[parent as usize].children = Some(id);
        for &c in children {
            self.scene.objects[c as usize].parent = Some(parent);
        }
        id
    }

    /// Links `child` to `parent` without listing it in the parent's children (yet).
    pub fn set_parent(&mut self, child: ObjectId, parent: ObjectId) -> &mut Self {
        self.scene.objects[child as usize].parent = Some(parent);
        self
    }

    /// A group/container of `kind` holding `children`.
    pub fn parent_of(&mut self, kind: &str, children: &[ObjectId]) -> ObjectId {
        let id = self.object(kind);
        self.children(id, children);
        id
    }

    pub fn build(mut self) -> Scene {
        self.scene.roots = self.scene.objects.iter().filter(|o| o.parent.is_none()).map(|o| o.id).collect();
        self.scene.duration = 10.0;
        self.scene
    }
}

pub fn object_list(ids: &[ObjectId]) -> Value {
    Value::List(ids.iter().map(|&i| Value::Object(i)).collect())
}

/// Chainable options on a [`Placement`].
pub trait PlacementOptions {
    fn gap(self, gap: f64) -> Self;
    fn margin(self, margin: f64) -> Self;
    fn align(self, align: &str) -> Self;
    fn clamped(self) -> Self;
}

impl PlacementOptions for Placement {
    fn gap(mut self, gap: f64) -> Self {
        self.gap = Some(constant(Value::Float(gap)));
        self
    }
    fn margin(mut self, margin: f64) -> Self {
        self.margin = Some(constant(Value::Float(margin)));
        self
    }
    fn align(mut self, align: &str) -> Self {
        self.align = Some(align.into());
        self
    }
    fn clamped(mut self) -> Self {
        self.clamp = true;
        self
    }
}

fn empty_placement() -> Placement {
    Placement {
        at: None,
        at_point: None,
        side: None,
        target: None,
        gap: None,
        margin: None,
        align: None,
        clamp: false,
        weak: false,
        rotated: false,
        span: Span::default(),
    }
}

/// `place(at="<anchor>")`.
pub fn at(anchor: &str) -> Placement {
    Placement { at: Some(anchor.into()), ..empty_placement() }
}

/// `place(at=(x, y))`.
pub fn at_point(x: f64, y: f64) -> Placement {
    Placement { at_point: Some(constant(Value::Vec2([x, y]))), ..empty_placement() }
}

/// `place(above=/below=/left_of=/right_of=/inside=target)`.
pub fn side(side: Side, target: ObjectId) -> Placement {
    Placement { side: Some(side), target: Some(target), ..empty_placement() }
}

pub fn constant(v: Value) -> Expr {
    Expr::Const { v }
}

pub fn derived(obj: ObjectId, prop: &str) -> Expr {
    Expr::Derived { obj, prop: prop.into(), world: false }
}

pub fn set(t: f64, src: Src) -> Entry {
    Entry::Set { t, src, span: Span::default() }
}

pub fn anim(t0: f64, t1: f64, to: Value, ease: Ease) -> Entry {
    Entry::Anim { t0, t1, to: Src::Val { v: to }, from: None, ease, blend: Blend::Replace, span: Span::default() }
}

/// Runs `f` with a fresh evaluator + layout over `scene`.
pub fn with_layout<R>(scene: &Scene, f: impl FnOnce(&Layout) -> R) -> R {
    let ev = Evaluator::new(scene);
    let layout = Layout::new(&ev);
    f(&layout)
}

pub fn assert_near(actual: f64, expected: f64) {
    assert!((actual - expected).abs() < 1e-6, "expected {expected}, got {actual}");
}

pub fn assert_v2(actual: [f64; 2], expected: [f64; 2]) {
    assert!(
        (actual[0] - expected[0]).abs() < 1e-6 && (actual[1] - expected[1]).abs() < 1e-6,
        "expected {expected:?}, got {actual:?}"
    );
}

pub fn assert_rect(actual: Rect, expected: [f64; 4]) {
    let a = [actual.x0, actual.y0, actual.x1, actual.y1];
    assert!(a.iter().zip(expected).all(|(x, e)| (x - e).abs() < 1e-6), "expected {expected:?}, got {a:?}");
}

/// Largest step between consecutive samples of `f` over `[t0, t1]` (n steps).
pub fn max_step(t0: f64, t1: f64, n: usize, f: impl Fn(f64) -> [f64; 2]) -> f64 {
    let mut prev = f(t0);
    let mut worst: f64 = 0.0;
    for i in 1..=n {
        let cur = f(t0 + (t1 - t0) * i as f64 / n as f64);
        worst = worst.max((cur[0] - prev[0]).hypot(cur[1] - prev[1]));
        prev = cur;
    }
    worst
}
