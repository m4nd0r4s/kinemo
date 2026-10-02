//! `vector_field`: arrows of a field `f(p) -> (vx, vy)` sampled on a grid.
//!
//! The grid has `density` columns across the region width (`x_range`) and as many
//! rows of the same spacing as fit in `y_range`; arrows sit at the cell centers. Each
//! arrow points along the field, with length `length · spacing · |v| / max|v|` (the
//! strongest arrow fills `length` of a cell) and a color mixed from `color_low` to
//! `color_high` by the same normalized magnitude.

use kinemo_eval::{color, PointContext};
use kinemo_ir::ObjectId;

use super::color_or;
use crate::Layout;

pub(crate) const DEFAULT_LOW: [f64; 4] = [0.30, 0.61, 0.91, 1.0];
pub(crate) const DEFAULT_HIGH: [f64; 4] = [0.96, 0.77, 0.26, 1.0];

/// One sampled arrow, in local coordinates.
#[derive(Clone, Debug, PartialEq)]
pub struct FieldArrow {
    pub start: [f64; 2],
    pub end: [f64; 2],
    /// `|v| / max|v|` over the grid, in `[0, 1]`.
    pub magnitude: f64,
    pub color: [f64; 4],
}

impl<'a> Layout<'a> {
    /// Grid cell centers of a `vector_field` leaf and the grid spacing.
    pub(crate) fn field_grid(&self, o: ObjectId, t: f64) -> (Vec<PointContext>, f64) {
        let region = self.mass_region(o, t);
        let cols = self.prop_f(o, "density", t, 30.0).round().clamp(1.0, 400.0) as usize;
        let spacing = region.width() / cols as f64;
        if spacing <= 0.0 {
            return (vec![], 0.0);
        }
        let rows = ((region.height() / spacing).floor() as usize).max(1);
        let y_offset = (region.height() - rows as f64 * spacing) / 2.0;
        let n = rows * cols;
        let mut out = Vec::with_capacity(n);
        for r in 0..rows {
            for c in 0..cols {
                let x = region.x0 + (c as f64 + 0.5) * spacing;
                let y = region.y0 + y_offset + (r as f64 + 0.5) * spacing;
                out.push(PointContext::new(x, y, out.len(), n));
            }
        }
        (out, spacing)
    }

    /// Every arrow of a `vector_field` leaf at `t` (zero vectors are skipped).
    pub fn field_arrows(&self, o: ObjectId, t: f64) -> Vec<FieldArrow> {
        let (grid, spacing) = self.field_grid(o, t);
        let vectors: Vec<[f64; 2]> = self.per_point(o, "field", t, &grid).iter().map(|v| v.as_v2()).collect();
        let max = vectors.iter().map(|v| v[0].hypot(v[1])).filter(|m| m.is_finite()).fold(0.0, f64::max);
        if max <= 0.0 {
            return vec![];
        }
        let length = self.prop_f(o, "length", t, 0.8) * spacing;
        let low = self.prop_color(o, "color_low", t).unwrap_or(DEFAULT_LOW);
        let high = self.prop_color(o, "color_high", t).unwrap_or(DEFAULT_HIGH);
        let colors = self.per_point(o, "color", t, &grid);
        grid.iter()
            .zip(vectors)
            .zip(colors)
            .filter_map(|((p, v), own)| {
                let m = v[0].hypot(v[1]);
                if !(m.is_finite() && m > 0.0) {
                    return None;
                }
                let magnitude = m / max;
                let half = [v[0] / m * length * magnitude / 2.0, v[1] / m * length * magnitude / 2.0];
                Some(FieldArrow {
                    start: [p.x - half[0], p.y - half[1]],
                    end: [p.x + half[0], p.y + half[1]],
                    magnitude,
                    color: color_or(&own, color::mix(low, high, magnitude)),
                })
            })
            .collect()
    }
}
