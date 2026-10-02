//! `k.Brace`: a curly brace along one side of a target's box, recomputed from the
//! target's layout at every time (so it follows the target as it moves or resizes).

use kurbo::{BezPath, Point, Rect};

use kinemo_ir::{ObjectId, Value};

use crate::geometry::{PartRole, ShapePart};
use crate::transform::transform_rect;
use crate::Layout;

/// Which side of the target the brace sits on (its tip points away from the target).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum BraceSide {
    Down,
    Up,
    Left,
    Right,
}

impl BraceSide {
    fn parse(name: &str) -> Self {
        match name {
            "up" | "top" | "above" => BraceSide::Up,
            "left" => BraceSide::Left,
            "right" => BraceSide::Right,
            _ => BraceSide::Down,
        }
    }
}

impl<'a> Layout<'a> {
    pub(crate) fn brace_parts(&self, o: ObjectId, t: f64) -> Vec<ShapePart> {
        let Some(Value::Object(target)) = self.prop(o, "target", t) else { return vec![] };
        if target == o {
            return vec![];
        }
        let parent = self.scene().object(o).parent;
        // Target box in the brace's own coordinates (its parent's, minus its translation).
        let in_parent = transform_rect(self.world_to_parent(parent, t), self.world_bbox(target, t));
        let [tx, ty] = self.translation(o, t);
        let target_box = in_parent - kurbo::Vec2::new(tx, ty);
        let side = BraceSide::parse(&self.prop_str(o, "direction", t).unwrap_or_default());
        let gap = self.prop_f(o, "gap", t, 0.1);
        let depth = self.prop_f(o, "depth", t, 0.25).max(0.0);
        let path = brace_path(target_box, side, gap, depth);
        vec![ShapePart::plain(path, PartRole::Shape)]
    }
}

/// Closed outline of a brace spanning one side of `target`, `gap` away from it.
pub(crate) fn brace_path(target: Rect, side: BraceSide, gap: f64, depth: f64) -> BezPath {
    let length = match side {
        BraceSide::Down | BraceSide::Up => target.width(),
        BraceSide::Left | BraceSide::Right => target.height(),
    };
    // Canonical frame: `u` along the span, `v` < 0 away from the target.
    let place = |u: f64, v: f64| match side {
        BraceSide::Down => Point::new(target.x0 + u, target.y0 - gap + v),
        BraceSide::Up => Point::new(target.x0 + u, target.y1 + gap - v),
        BraceSide::Left => Point::new(target.x0 - gap + v, target.y0 + u),
        BraceSide::Right => Point::new(target.x1 + gap - v, target.y0 + u),
    };
    let mut path = BezPath::new();
    if length <= 1e-9 || depth <= 1e-9 {
        return path;
    }
    let depth = depth.min(length / 2.0);
    let thickness = depth * 0.25;
    let corner = (depth / 2.0).min(length / 4.0);
    let mid = length / 2.0;
    let arm = -depth / 2.0;
    let inner_arm = arm + thickness;
    let inner_tip = -depth + 2.0 * thickness;

    // Outer edge, left to right.
    path.move_to(place(0.0, 0.0));
    path.quad_to(place(0.0, arm), place(corner, arm));
    path.line_to(place(mid - corner, arm));
    path.quad_to(place(mid, arm), place(mid, -depth));
    path.quad_to(place(mid, arm), place(mid + corner, arm));
    path.line_to(place(length - corner, arm));
    path.quad_to(place(length, arm), place(length, 0.0));
    // Inner edge, right to left (thinner at the ends, notched at the tip).
    path.quad_to(place(length - thickness, inner_arm), place(length - corner, inner_arm));
    path.line_to(place(mid + corner, inner_arm));
    path.quad_to(place(mid, inner_arm), place(mid, inner_tip));
    path.quad_to(place(mid, inner_arm), place(mid - corner, inner_arm));
    path.line_to(place(corner, inner_arm));
    path.quad_to(place(thickness, inner_arm), place(0.0, 0.0));
    path.close_path();
    path
}

#[cfg(test)]
mod tests {
    use super::*;
    use kurbo::Shape;

    #[test]
    fn brace_spans_the_side_and_points_away() {
        let target = Rect::new(-1.0, -0.5, 1.0, 0.5);
        let down = brace_path(target, BraceSide::Down, 0.1, 0.2).bounding_box();
        assert!((down.x0 + 1.0).abs() < 1e-9 && (down.x1 - 1.0).abs() < 1e-9);
        assert!((down.y1 - (-0.6)).abs() < 1e-9 && (down.y0 - (-0.8)).abs() < 1e-9);
        let right = brace_path(target, BraceSide::Right, 0.1, 0.2).bounding_box();
        assert!((right.x0 - 1.1).abs() < 1e-9 && (right.x1 - 1.3).abs() < 1e-9);
        assert!((right.y0 + 0.5).abs() < 1e-9 && (right.y1 - 0.5).abs() < 1e-9);
    }

    #[test]
    fn empty_target_draws_nothing() {
        assert!(brace_path(Rect::ZERO, BraceSide::Up, 0.1, 0.2).elements().is_empty());
    }
}
