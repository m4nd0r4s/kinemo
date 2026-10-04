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
                let (old, new) = (obj_list(&from), obj_list(&to));
                let a = self.arrange(c, &old, t);
                let b = self.arrange(c, &new, t);
                let vertical = self.scene().object(c).kind == "column";
                let across = |id: ObjectId| {
                    let r = self.shape_box(id, t);
                    if vertical { r.width() } else { r.height() }
                };
                let axis = usize::from(vertical);
                let travel = |id: ObjectId| (b[&id][axis] - a[&id][axis]).abs();
                // Each pair that passes clears exactly: they step aside by half their summed
                // size, shared in proportion to how far each one travels.
                let mut clearance: HashMap<ObjectId, f64> = HashMap::new();
                for (x, y) in crossing(&old, &new) {
                    let needed = (across(x) + across(y)) / 2.0;
                    let total = travel(x) + travel(y);
                    if total < 1e-9 {
                        continue;
                    }
                    for (id, share) in [(x, travel(x) / total), (y, travel(y) / total)] {
                        let entry = clearance.entry(id).or_insert(0.0);
                        *entry = entry.max(needed * share);
                    }
                }
                with_crossings_apart(blend(&a, &b, alpha), &a, &b, &clearance, alpha, vertical)
            }
        };
        self.store_arrangement(c, t, a.clone());
        a
    }

    /// Box of a group during a change of its children (`row.insert`, a table's new rows):
    /// between the box of the old children and the box of the new ones, so a placed group
    /// slides instead of jumping. `None` outside such transitions.
    pub(crate) fn reorder_bbox(&self, c: ObjectId, t: f64) -> Option<Rect> {
        let Evaluated::Transition { from, to, alpha } = self.children_raw(c, t) else { return None };
        let container = is_container(&self.scene().object(c).kind);
        let bounds = |children: &[ObjectId]| -> Rect {
            let slots = container.then(|| self.arrange(c, children, t));
            children
                .iter()
                .filter(|&&child| self.takes_space(child, t))
                .map(|child| match &slots {
                    Some(slots) => {
                        let [x, y] = slots[child];
                        self.shape_box(*child, t) + kurbo::Vec2::new(x, y)
                    }
                    None => self.parent_box(*child, t),
                })
                .reduce(|a, b| a.union(b))
                .unwrap_or(Rect::ZERO)
        };
        let (a, b) = (bounds(&obj_list(&from)), bounds(&obj_list(&to)));
        let mix = |p: f64, q: f64| p + (q - p) * alpha;
        Some(Rect::new(mix(a.x0, b.x0), mix(a.y0, b.y0), mix(a.x1, b.x1), mix(a.y1, b.y1)))
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

/// Pairs of children whose relative order changes: they pass each other.
fn crossing(old: &[ObjectId], new: &[ObjectId]) -> Vec<(ObjectId, ObjectId)> {
    let rank = |list: &[ObjectId], id: ObjectId| list.iter().position(|&x| x == id);
    let both: Vec<ObjectId> = old.iter().copied().filter(|id| new.contains(id)).collect();
    let mut out = Vec::new();
    for (i, &x) in both.iter().enumerate() {
        for &y in &both[i + 1..] {
            let before = rank(old, x) < rank(old, y);
            let after = rank(new, x) < rank(new, y);
            if before != after {
                out.push((x, y));
            }
        }
    }
    out
}

/// Largest sideways step of a child passing another (units).
const MAX_CLEARANCE: f64 = 1.6;

/// Children that pass each other travel on opposite arcs (forward over, backward under)
/// instead of through each other. `clearance` holds how far each one steps aside at the
/// halfway point.
fn with_crossings_apart(mut out: Arrangement, a: &Arrangement, b: &Arrangement, clearance: &HashMap<ObjectId, f64>, alpha: f64, vertical: bool) -> Arrangement {
    // Up quickly and level while the children overlap along the flow, then back down.
    let lift = ((alpha * std::f64::consts::PI).sin() * 1.8).min(1.0);
    for (id, &aside) in clearance {
        let (Some(pa), Some(pb), Some(p)) = (a.get(id), b.get(id), out.get_mut(id)) else { continue };
        let axis = if vertical { 1 } else { 0 };
        let travel = pb[axis] - pa[axis];
        if travel.abs() < 1e-9 {
            continue;
        }
        let step = travel.signum() * aside.min(MAX_CLEARANCE) * lift;
        if vertical {
            p[0] -= step;
        } else {
            p[1] += step;
        }
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
    fn swapped_children_pass_on_opposite_arcs() {
        let a: Arrangement = [(1, [0.0, 0.0]), (2, [2.0, 0.0]), (3, [4.0, 0.0])].into_iter().collect();
        let b: Arrangement = [(1, [0.0, 0.0]), (2, [4.0, 0.0]), (3, [2.0, 0.0])].into_iter().collect();
        let clearance: HashMap<ObjectId, f64> = crossing(&[1, 2, 3], &[1, 3, 2]).into_iter().flat_map(|(x, y)| [(x, 0.5), (y, 0.5)]).collect();
        let mid = with_crossings_apart(blend(&a, &b, 0.5), &a, &b, &clearance, 0.5, false);
        assert!((mid[&2][1] - 0.5).abs() < 1e-9 && (mid[&3][1] + 0.5).abs() < 1e-9);
        assert_eq!(mid[&1], [0.0, 0.0]);
        assert!(crossing(&[1, 2], &[1, 2, 3]).is_empty());
    }

    #[test]
    fn blend_midpoint() {
        let a: Arrangement = [(1, [0.0, 0.0])].into_iter().collect();
        let b: Arrangement = [(1, [2.0, 0.0])].into_iter().collect();
        assert_eq!(blend(&a, &b, 0.5)[&1], [1.0, 0.0]);
    }
}
