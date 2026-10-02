//! Relative constraints: `place(at=, above=, below=, left_of=, right_of=, inside=, ...)`.
//!
//! Constraints are directional (the placed object depends on its target), so they are
//! solved by memoized recursion; loops are detected by the engine and reported as K0402.

use kurbo::{Point, Rect};

use kinemo_ir::{ObjectId, Placement, Side, Value};

use crate::transform::{anchor_unit, frame_rect, transform_rect, unit_point};
use crate::Layout;

const DEFAULT_GAP: f64 = 0.25;
const DEFAULT_MARGIN: f64 = 0.5;
const SAFE_MARGIN: f64 = 0.5;

impl<'a> Layout<'a> {
    /// Translation from the placement timeline, blending across placement changes.
    pub(crate) fn placed_position(&self, o: ObjectId, t: f64, free: [f64; 2]) -> Option<[f64; 2]> {
        self.placed_position_from(o, self.scene().object(o).place.len(), t, free)
    }

    /// Position given by the first `count` placement entries. A blend starts from what the
    /// earlier entries give (itself possibly still blending), so interruptions don't jump.
    fn placed_position_from(&self, o: ObjectId, count: usize, t: f64, free: [f64; 2]) -> Option<[f64; 2]> {
        let entries = &self.scene().object(o).place[..count];
        let i = entries.iter().rposition(|e| e.t <= t)?;
        let e = &entries[i];
        let cur = self.solve_or_free(o, e.p.as_ref(), t, free);
        if e.dur > 0.0 && t < e.t + e.dur {
            let prev = self.placed_position_from(o, i, t, free).unwrap_or(free);
            let a = kinemo_eval::ease::apply(&e.ease, (t - e.t) / e.dur);
            return Some([prev[0] + (cur[0] - prev[0]) * a, prev[1] + (cur[1] - prev[1]) * a]);
        }
        e.p.as_ref()?;
        Some(cur)
    }

    fn solve_or_free(&self, o: ObjectId, p: Option<&Placement>, t: f64, free: [f64; 2]) -> [f64; 2] {
        p.map_or(free, |p| self.solve(o, p, t))
    }

    fn num(&self, e: &Option<kinemo_ir::Expr>, t: f64, default: f64) -> f64 {
        match e {
            Some(e) => match self.ev.expr(e, t, self) {
                Value::None => default,
                v => v.as_f64(),
            },
            None => default,
        }
    }

    /// Box of `target` expressed in the coordinates of `parent`.
    fn box_in(&self, target: ObjectId, parent: Option<ObjectId>, t: f64) -> Rect {
        if self.scene().object(target).parent == parent {
            self.parent_box(target, t)
        } else {
            transform_rect(self.world_to_parent(parent, t), self.world_bbox(target, t))
        }
    }

    fn solve(&self, o: ObjectId, p: &Placement, t: f64) -> [f64; 2] {
        let parent = self.scene().object(o).parent;
        let b = self.shape_box(o, t);
        let align = p.align.as_deref().unwrap_or("center");
        let mut out = if let (Some(side), Some(target)) = (&p.side, p.target) {
            let tb = self.box_in(target, parent, t);
            let gap = self.num(&p.gap, t, if *side == Side::Inside { 0.0 } else { DEFAULT_GAP });
            side_position(side, b, tb, gap, align)
        } else if let Some(pt) = &p.at_point {
            let [x, y] = self.ev.expr(pt, t, self).as_v2();
            let local = self.world_to_parent(parent, t) * Point::new(x, y);
            let c = b.center();
            [local.x - c.x, local.y - c.y]
        } else {
            let at = p.at.as_deref().unwrap_or("center");
            let m = self.num(&p.margin, t, if at == "center" { 0.0 } else { DEFAULT_MARGIN });
            let frame = self.frame_in(parent, t).inset(-m);
            let u = anchor_unit(at);
            let (target, own) = (unit_point(frame, u), unit_point(b, u));
            [target.x - own.x, target.y - own.y]
        };
        if p.clamp {
            out = clamp_into(b, out, self.frame_in(parent, t).inset(-SAFE_MARGIN));
        }
        out
    }

    fn frame_in(&self, parent: Option<ObjectId>, t: f64) -> Rect {
        transform_rect(self.world_to_parent(parent, t), frame_rect(&self.scene().config))
    }
}

fn side_position(side: &Side, b: Rect, tb: Rect, gap: f64, align: &str) -> [f64; 2] {
    let u = anchor_unit(align);
    let along_x = || unit_point(tb, [u[0], 0.0]).x - unit_point(b, [u[0], 0.0]).x;
    let along_y = || unit_point(tb, [0.0, u[1]]).y - unit_point(b, [0.0, u[1]]).y;
    match side {
        Side::Above => [along_x(), tb.y1 + gap - b.y0],
        Side::Below => [along_x(), tb.y0 - gap - b.y1],
        Side::LeftOf => [tb.x0 - gap - b.x1, along_y()],
        Side::RightOf => [tb.x1 + gap - b.x0, along_y()],
        Side::Inside => {
            let inner = tb.inset(-gap);
            let (target, own) = (unit_point(inner, u), unit_point(b, u));
            [target.x - own.x, target.y - own.y]
        }
    }
}

fn clamp_into(b: Rect, pos: [f64; 2], area: Rect) -> [f64; 2] {
    let moved = b + kurbo::Vec2::new(pos[0], pos[1]);
    let shift = |lo: f64, hi: f64, alo: f64, ahi: f64| {
        if hi - lo > ahi - alo {
            (alo + ahi) / 2.0 - (lo + hi) / 2.0
        } else if lo < alo {
            alo - lo
        } else if hi > ahi {
            ahi - hi
        } else {
            0.0
        }
    };
    [
        pos[0] + shift(moved.x0, moved.x1, area.x0, area.x1),
        pos[1] + shift(moved.y0, moved.y1, area.y0, area.y1),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r(x0: f64, y0: f64, x1: f64, y1: f64) -> Rect {
        Rect::new(x0, y0, x1, y1)
    }

    #[test]
    fn above_centers_and_gaps() {
        let p = side_position(&Side::Above, r(-1.0, -0.5, 1.0, 0.5), r(2.0, 0.0, 4.0, 1.0), 0.25, "center");
        assert_eq!(p, [3.0, 1.75]);
    }

    #[test]
    fn inside_bottom_with_pad() {
        let p = side_position(&Side::Inside, r(-0.5, -0.5, 0.5, 0.5), r(-1.0, -2.0, 1.0, 2.0), 0.1, "bottom");
        assert!((p[1] - (-1.4)).abs() < 1e-12);
        assert_eq!(p[0], 0.0);
    }

    #[test]
    fn clamp_pulls_inside() {
        let p = clamp_into(r(-1.0, -1.0, 1.0, 1.0), [10.0, 0.0], r(-7.5, -4.0, 7.5, 4.0));
        assert_eq!(p, [6.5, 0.0]);
    }
}
