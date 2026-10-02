//! Traversal of the scene graph in draw order.

use kinemo_ir::ObjectId;
use kinemo_layout::Layout;

/// Present leaves at `t`, sorted by accumulated `z` and then tree order.
pub(crate) fn leaves(layout: &Layout, t: f64) -> Vec<ObjectId> {
    let scene = layout.scene();
    let mut out: Vec<(f64, usize, ObjectId)> = Vec::new();
    let mut order = 0usize;
    let mut stack: Vec<(ObjectId, f64)> = scene.roots.iter().rev().map(|&r| (r, 0.0)).collect();
    while let Some((o, z_parent)) = stack.pop() {
        if !layout.prop_bool(o, "visible", t, true) {
            continue;
        }
        let z = z_parent + layout.prop_f(o, "z", t, 0.0);
        if scene.object(o).children.is_some() {
            for c in layout.children(o, t).into_iter().rev() {
                stack.push((c, z));
            }
        } else if scene.present(o, t) {
            out.push((z, order, o));
            order += 1;
        }
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
    out.into_iter().map(|(_, _, o)| o).collect()
}
