//! Containers: `Row`, `Column`, `Grid` and `Stack` arrange their children.
//!
//! Reordering (`row.swap`, `row.insert`, ...) animates the `children` signal; during the
//! transition each child blends between its slot in the old and in the new arrangement.

use std::collections::HashMap;

use kurbo::Rect;

use kinemo_eval::Evaluated;
use kinemo_ir::ObjectId;

use crate::props::obj_list;
use crate::Layout;

pub(crate) type Arrangement = HashMap<ObjectId, [f64; 2]>;

pub(crate) fn is_container(kind: &str) -> bool {
    matches!(kind, "row" | "column" | "grid" | "stack")
}

impl<'a> Layout<'a> {
    /// Translation imposed by the parent container, if the parent is one.
    pub(crate) fn container_position(&self, o: ObjectId, t: f64) -> Option<[f64; 2]> {
        let parent = self.scene().object(o).parent?;
        if !is_container(&self.scene().object(parent).kind) {
            return None;
        }
        self.arrangement(parent, t).get(&o).copied()
    }

    fn arrangement(&self, c: ObjectId, t: f64) -> Arrangement {
        if let Some(a) = self.cached_arrangement(c, t) {
            return a;
        }
        let a = match self.children_raw(c, t) {
            Evaluated::Value(v) => self.arrange(c, &obj_list(&v), t),
            Evaluated::Transition { from, to, alpha } => {
                let a = self.arrange(c, &obj_list(&from), t);
                let b = self.arrange(c, &obj_list(&to), t);
                blend(&a, &b, alpha)
            }
        };
        self.store_arrangement(c, t, a.clone());
        a
    }

    fn arrange(&self, c: ObjectId, children: &[ObjectId], t: f64) -> Arrangement {
        let kind = self.scene().object(c).kind.clone();
        let gap = self.prop_f(c, "gap", t, 0.25);
        let align = self.prop_str(c, "align", t).unwrap_or_else(|| "center".into());
        let boxes: Vec<Rect> = children.iter().map(|&ch| self.shape_box(ch, t)).collect();
        let slots = match kind.as_str() {
            "row" => line(&boxes, gap, &align, true),
            "column" => line(&boxes, gap, &align, false),
            "grid" => grid(&boxes, gap, self.prop_f(c, "cols", t, 3.0).max(1.0) as usize),
            _ => stack(&boxes, &align),
        };
        children.iter().copied().zip(slots).collect()
    }
}

fn blend(a: &Arrangement, b: &Arrangement, alpha: f64) -> Arrangement {
    let mut out = b.clone();
    for (id, pb) in out.iter_mut() {
        if let Some(pa) = a.get(id) {
            *pb = [pa[0] + (pb[0] - pa[0]) * alpha, pa[1] + (pb[1] - pa[1]) * alpha];
        }
    }
    for (id, pa) in a {
        out.entry(*id).or_insert(*pa);
    }
    out
}

/// Row (horizontal) or column (vertical) arrangement centered on the origin.
fn line(boxes: &[Rect], gap: f64, align: &str, horizontal: bool) -> Vec<[f64; 2]> {
    let main = |r: &Rect| if horizontal { r.width() } else { r.height() };
    let cross = |r: &Rect| if horizontal { r.height() } else { r.width() };
    let total: f64 = boxes.iter().map(main).sum::<f64>() + gap * boxes.len().saturating_sub(1) as f64;
    let extent = boxes.iter().map(cross).fold(0.0, f64::max);
    let mut cursor = -total / 2.0;
    boxes
        .iter()
        .map(|b| {
            let pos = if horizontal {
                let tx = cursor - b.x0;
                let ty = match align {
                    "bottom" => -extent / 2.0 - b.y0,
                    "top" => extent / 2.0 - b.y1,
                    _ => -b.center().y,
                };
                [tx, ty]
            } else {
                let ty = -cursor - b.y1;
                let tx = match align {
                    "left" => -extent / 2.0 - b.x0,
                    "right" => extent / 2.0 - b.x1,
                    _ => -b.center().x,
                };
                [tx, ty]
            };
            cursor += main(b) + gap;
            pos
        })
        .collect()
}

fn grid(boxes: &[Rect], gap: f64, cols: usize) -> Vec<[f64; 2]> {
    let cw = boxes.iter().map(|b| b.width()).fold(0.0, f64::max);
    let ch = boxes.iter().map(|b| b.height()).fold(0.0, f64::max);
    let cols = cols.min(boxes.len().max(1));
    let rows = boxes.len().div_ceil(cols);
    let w = cols as f64 * cw + gap * cols.saturating_sub(1) as f64;
    let h = rows as f64 * ch + gap * rows.saturating_sub(1) as f64;
    boxes
        .iter()
        .enumerate()
        .map(|(i, b)| {
            let (r, c) = (i / cols, i % cols);
            let cx = -w / 2.0 + cw / 2.0 + c as f64 * (cw + gap);
            let cy = h / 2.0 - ch / 2.0 - r as f64 * (ch + gap);
            [cx - b.center().x, cy - b.center().y]
        })
        .collect()
}

fn stack(boxes: &[Rect], align: &str) -> Vec<[f64; 2]> {
    let w = boxes.iter().map(|b| b.width()).fold(0.0, f64::max);
    let h = boxes.iter().map(|b| b.height()).fold(0.0, f64::max);
    let outer = Rect::new(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0);
    let [ux, uy] = crate::transform::anchor_unit(align);
    boxes
        .iter()
        .map(|b| {
            let target = crate::transform::unit_point(outer, [ux, uy]);
            let own = crate::transform::unit_point(*b, [ux, uy]);
            [target.x - own.x, target.y - own.y]
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sq(s: f64) -> Rect {
        Rect::new(-s / 2.0, -s / 2.0, s / 2.0, s / 2.0)
    }

    #[test]
    fn row_is_centered_and_gapped() {
        let p = line(&[sq(1.0), sq(1.0)], 0.5, "center", true);
        assert_eq!(p, vec![[-0.75, 0.0], [0.75, 0.0]]);
    }

    #[test]
    fn row_bottom_alignment() {
        let p = line(&[sq(1.0), sq(2.0)], 0.0, "bottom", true);
        assert!((p[0][1] - -0.5).abs() < 1e-12);
        assert!((p[1][1] - 0.0).abs() < 1e-12);
    }

    #[test]
    fn column_goes_down() {
        let p = line(&[sq(1.0), sq(1.0)], 0.0, "center", false);
        assert!(p[0][1] > p[1][1]);
    }

    #[test]
    fn grid_cells() {
        let p = grid(&[sq(1.0), sq(1.0), sq(1.0), sq(1.0)], 0.0, 2);
        assert_eq!(p[0], [-0.5, 0.5]);
        assert_eq!(p[3], [0.5, -0.5]);
    }

    #[test]
    fn blend_midpoint() {
        let a: Arrangement = [(1, [0.0, 0.0])].into_iter().collect();
        let b: Arrangement = [(1, [2.0, 0.0])].into_iter().collect();
        assert_eq!(blend(&a, &b, 0.5)[&1], [1.0, 0.0]);
    }
}
