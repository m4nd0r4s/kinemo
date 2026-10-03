//! Transforms: pivoted rotate/scale, translation, and render-only entry effects.

use kurbo::{Affine, Point, Rect, Vec2};

use kinemo_ir::{ObjectId, SceneConfig};

use crate::Layout;

/// The visible frame in world coordinates (origin at the center, y up).
pub fn frame_rect(cfg: &SceneConfig) -> Rect {
    Rect::new(-cfg.frame_w / 2.0, -cfg.frame_h / 2.0, cfg.frame_w / 2.0, cfg.frame_h / 2.0)
}

/// Point of `r` named by an anchor ("center", "top", "bottom-left", ...). Unknown names → center.
pub fn anchor_point(r: Rect, name: &str) -> Point {
    let [ux, uy] = anchor_unit(name);
    unit_point(r, [ux, uy])
}

/// Anchor name as relative coordinates in [-1, 1]² (y up).
pub(crate) fn anchor_unit(name: &str) -> [f64; 2] {
    let mut u = [0.0, 0.0];
    for part in name.split('-') {
        match part {
            "top" => u[1] = 1.0,
            "bottom" => u[1] = -1.0,
            "left" => u[0] = -1.0,
            "right" => u[0] = 1.0,
            _ => {}
        }
    }
    u
}

/// Point at relative coordinates `u` ∈ [-1, 1]² inside `r`.
pub(crate) fn unit_point(r: Rect, u: [f64; 2]) -> Point {
    let c = r.center();
    Point::new(c.x + u[0] * r.width() / 2.0, c.y + u[1] * r.height() / 2.0)
}

pub(crate) fn transform_rect(a: Affine, r: Rect) -> Rect {
    let pts = [
        Point::new(r.x0, r.y0),
        Point::new(r.x1, r.y0),
        Point::new(r.x0, r.y1),
        Point::new(r.x1, r.y1),
    ]
    .map(|p| a * p);
    let mut out = Rect::from_points(pts[0], pts[1]);
    out = out.union_pt(pts[2]);
    out.union_pt(pts[3])
}

impl<'a> Layout<'a> {
    /// Rotation and scale about the object's anchor, without translation.
    pub fn shape_affine(&self, o: ObjectId, t: f64) -> Affine {
        let s = self.prop_f(o, "scale", t, 1.0);
        let sx = self.prop_f(o, "scale_x", t, 1.0) * s;
        let sy = self.prop_f(o, "scale_y", t, 1.0) * s;
        let rot = self.prop_f(o, "rotate", t, 0.0);
        if sx == 1.0 && sy == 1.0 && rot == 0.0 {
            return Affine::IDENTITY;
        }
        let pivot = unit_point(self.local_bbox(o, t), self.prop_v2(o, "anchor", t, [0.0, 0.0]));
        let pv = pivot.to_vec2();
        Affine::translate(pv)
            * Affine::rotate(rot.to_radians())
            * Affine::scale_non_uniform(sx, sy)
            * Affine::translate(-pv)
    }

    /// Transform from the object's local coordinates to its parent's coordinates.
    pub fn local_affine(&self, o: ObjectId, t: f64) -> Affine {
        let [x, y] = self.translation(o, t);
        Affine::translate(Vec2::new(x, y)) * self.shape_affine(o, t)
    }

    /// Box the object occupies relative to its own translation (rotate/scale applied).
    pub(crate) fn shape_box(&self, o: ObjectId, t: f64) -> Rect {
        transform_rect(self.shape_affine(o, t), self.local_bbox(o, t))
    }

    /// Box the object occupies in its parent's coordinates.
    pub fn parent_box(&self, o: ObjectId, t: f64) -> Rect {
        transform_rect(self.local_affine(o, t), self.local_bbox(o, t))
    }

    /// Render-only effects of verbs (`grow`, `fade_in(shift=)`, `indicate`, `squash`): they never
    /// move layout dependents.
    pub fn effect_affine(&self, o: ObjectId, t: f64) -> Affine {
        let g = self.prop_f(o, "_grow", t, 1.0);
        let [dx, dy] = self.prop_v2(o, "_shift", t, [0.0, 0.0]);
        let mut a = Affine::translate(Vec2::new(dx, dy));
        let squash = self.prop_f(o, "_squash", t, 0.0);
        if squash != 0.0 {
            // Elastic squash: shorter and wider, resting on its base.
            let b = self.local_bbox(o, t);
            let base = kurbo::Vec2::new(b.center().x, b.y0);
            a = a * Affine::translate(base) * Affine::scale_non_uniform(1.0 + squash / 2.0, 1.0 - squash) * Affine::translate(-base);
        }
        let pulse = self.prop_f(o, "_pulse", t, 1.0);
        if pulse != 1.0 {
            // About the box center, or the point `_pulse_from` names (a bar pulses from its base).
            let from = self.prop_v2(o, "_pulse_from", t, [0.0, 0.0]);
            let c = unit_point(self.local_bbox(o, t), from).to_vec2();
            a = a * Affine::translate(c) * Affine::scale(pulse) * Affine::translate(-c);
        }
        if g != 1.0 {
            let from = self.prop_v2(o, "_grow_from", t, [0.0, 0.0]);
            let pivot = unit_point(self.local_bbox(o, t), from).to_vec2();
            a = a * Affine::translate(pivot) * Affine::scale(g.max(0.0)) * Affine::translate(-pivot);
        }
        a
    }
}
