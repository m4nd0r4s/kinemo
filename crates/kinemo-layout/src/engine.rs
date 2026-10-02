//! The layout engine: memoized per-time queries over the scene graph.

use std::cell::RefCell;
use std::collections::{HashMap, HashSet};

use kurbo::{Affine, Rect};

use kinemo_eval::{Evaluator, Resolver};
use kinemo_ir::{ObjectId, Scene, Value};

use crate::container::Arrangement;
use crate::diag::{LayoutIssue, LayoutIssueKind};
use crate::transform::transform_rect;

type Key = (ObjectId, u64);

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) enum Query {
    Bbox,
    Translation,
}

/// Layout queries for one scene. Results are memoized per (object, time).
pub struct Layout<'a> {
    pub(crate) ev: &'a Evaluator<'a>,
    bbox: RefCell<HashMap<Key, Rect>>,
    translation: RefCell<HashMap<Key, [f64; 2]>>,
    arrangements: RefCell<HashMap<Key, Arrangement>>,
    active: RefCell<HashSet<(Query, ObjectId, u64)>>,
    issues: RefCell<Vec<LayoutIssue>>,
}

impl<'a> Layout<'a> {
    pub fn new(ev: &'a Evaluator<'a>) -> Self {
        Layout {
            ev,
            bbox: RefCell::default(),
            translation: RefCell::default(),
            arrangements: RefCell::default(),
            active: RefCell::default(),
            issues: RefCell::default(),
        }
    }

    pub fn scene(&self) -> &'a Scene {
        self.ev.scene()
    }

    pub fn evaluator(&self) -> &'a Evaluator<'a> {
        self.ev
    }

    /// Drop memoized results (e.g. between frames when memory matters).
    pub fn clear(&self) {
        self.bbox.borrow_mut().clear();
        self.translation.borrow_mut().clear();
        self.arrangements.borrow_mut().clear();
    }

    /// Problems found while resolving (cycles, contradictions), deduplicated.
    pub fn issues(&self) -> Vec<LayoutIssue> {
        self.issues.borrow().clone()
    }

    pub(crate) fn report(&self, issue: LayoutIssue) {
        let mut issues = self.issues.borrow_mut();
        if !issues.iter().any(|i| i.kind == issue.kind && i.objects == issue.objects) {
            issues.push(issue);
        }
    }

    /// Runs `f` unless the same query is already in progress (a cycle), in which case
    /// the cycle is reported and `fallback` is returned.
    pub(crate) fn guarded<T>(&self, q: Query, o: ObjectId, t: f64, fallback: T, f: impl FnOnce() -> T) -> T {
        let key = (q, o, t.to_bits());
        if !self.active.borrow_mut().insert(key) {
            let chain: Vec<ObjectId> = self
                .active
                .borrow()
                .iter()
                .filter(|(qq, _, tt)| *qq == Query::Translation && *tt == t.to_bits())
                .map(|(_, id, _)| *id)
                .collect();
            let mut objects = chain;
            objects.sort_unstable();
            self.report(LayoutIssue { kind: LayoutIssueKind::Cycle, objects, t });
            return fallback;
        }
        let out = f();
        self.active.borrow_mut().remove(&key);
        out
    }

    pub(crate) fn cached_arrangement(&self, c: ObjectId, t: f64) -> Option<Arrangement> {
        self.arrangements.borrow().get(&(c, t.to_bits())).cloned()
    }

    pub(crate) fn store_arrangement(&self, c: ObjectId, t: f64, a: Arrangement) {
        self.arrangements.borrow_mut().insert((c, t.to_bits()), a);
    }

    /// Bounding box in the object's own coordinates (visible children included, transformed).
    pub fn local_bbox(&self, o: ObjectId, t: f64) -> Rect {
        let key = (o, t.to_bits());
        if let Some(r) = self.bbox.borrow().get(&key) {
            return *r;
        }
        let r = self.guarded(Query::Bbox, o, t, Rect::ZERO, || {
            if self.scene().object(o).children.is_some() {
                self.children(o, t)
                    .into_iter()
                    .filter(|&c| self.prop_bool(c, "visible", t, true))
                    .map(|c| self.parent_box(c, t))
                    .reduce(|a, b| a.union(b))
                    .unwrap_or(Rect::ZERO)
            } else {
                self.leaf_bbox(o, t)
            }
        });
        self.bbox.borrow_mut().insert(key, r);
        r
    }

    /// Translation of the object in its parent's coordinates, after containers and
    /// constraints.
    pub fn translation(&self, o: ObjectId, t: f64) -> [f64; 2] {
        let key = (o, t.to_bits());
        if let Some(v) = self.translation.borrow().get(&key) {
            return *v;
        }
        let free = [self.prop_f(o, "x", t, 0.0), self.prop_f(o, "y", t, 0.0)];
        let v = self.guarded(Query::Translation, o, t, free, || {
            if let Some(p) = self.container_position(o, t) {
                p
            } else if let Some(p) = self.placed_position(o, t, free) {
                p
            } else {
                free
            }
        });
        self.translation.borrow_mut().insert(key, v);
        v
    }

    /// Parent chain transform: local → world, without render effects.
    pub fn world_affine(&self, o: ObjectId, t: f64) -> Affine {
        let local = self.local_affine(o, t);
        match self.scene().object(o).parent {
            Some(p) => self.world_affine(p, t) * local,
            None => local,
        }
    }

    /// Local → world including the render-only effects of ancestors and the object.
    pub fn render_affine(&self, o: ObjectId, t: f64) -> Affine {
        let own = self.local_affine(o, t) * self.effect_affine(o, t);
        match self.scene().object(o).parent {
            Some(p) => self.render_affine(p, t) * own,
            None => own,
        }
    }

    pub fn world_bbox(&self, o: ObjectId, t: f64) -> Rect {
        transform_rect(self.world_affine(o, t), self.local_bbox(o, t))
    }

    /// Affine mapping world coordinates into the coordinates of `parent` (identity for roots).
    pub(crate) fn world_to_parent(&self, parent: Option<ObjectId>, t: f64) -> Affine {
        match parent {
            Some(p) => self.world_affine(p, t).inverse(),
            None => Affine::IDENTITY,
        }
    }

    /// Value of a layout-derived prop (`x`, `left`, `width`, `center`, `bbox`, ...).
    pub fn derived(&self, o: ObjectId, prop: &str, world: bool, t: f64) -> Value {
        let b = if world { self.world_bbox(o, t) } else { self.parent_box(o, t) };
        let c = b.center();
        match prop {
            "x" | "y" | "position" => {
                let [x, y] = if world {
                    let p = self.world_affine(o, t) * kurbo::Point::ZERO;
                    [p.x, p.y]
                } else {
                    self.translation(o, t)
                };
                match prop {
                    "x" => Value::Float(x),
                    "y" => Value::Float(y),
                    _ => Value::Vec2([x, y]),
                }
            }
            "width" => Value::Float(b.width()),
            "height" => Value::Float(b.height()),
            "left" => Value::Float(b.x0),
            "right" => Value::Float(b.x1),
            "bottom" => Value::Float(b.y0),
            "top" => Value::Float(b.y1),
            "center" => Value::Vec2([c.x, c.y]),
            "bbox" => Value::List(vec![Value::Vec2([b.x0, b.y0]), Value::Vec2([b.x1, b.y1])]),
            _ => Value::None,
        }
    }

    /// Time since the object (or its nearest present ancestor) last entered the scene.
    pub fn age(&self, o: ObjectId, t: f64) -> f64 {
        let mut cur = Some(o);
        while let Some(id) = cur {
            let obj = self.scene().object(id);
            if let Some(enter) = last_enter(&obj.presence, t) {
                return t - enter;
            }
            cur = obj.parent;
        }
        0.0
    }
}

fn last_enter(presence: &[(f64, bool)], t: f64) -> Option<f64> {
    let mut enter = None;
    for (pt, present) in presence {
        if *pt > t {
            break;
        }
        enter = if *present { enter.or(Some(*pt)) } else { None };
    }
    enter
}

impl<'a> Resolver for Layout<'a> {
    fn derived(&self, _ev: &Evaluator, obj: ObjectId, prop: &str, world: bool, t: f64) -> Value {
        Layout::derived(self, obj, prop, world, t)
    }

    fn age(&self, _ev: &Evaluator, obj: ObjectId, t: f64) -> f64 {
        Layout::age(self, obj, t)
    }

    fn to_world(&self, _ev: &Evaluator, obj: ObjectId, point: [f64; 2], t: f64) -> [f64; 2] {
        let p = self.world_affine(obj, t) * kurbo::Point::new(point[0], point[1]);
        [p.x, p.y]
    }
}
