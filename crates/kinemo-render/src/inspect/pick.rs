//! Pixel picking: the topmost drawn object under a pixel of a rendered frame.

use kurbo::{Point, Rect, Shape};

use kinemo_eval::Evaluator;
use kinemo_ir::{ObjectId, Scene};
use kinemo_layout::Layout;

use crate::frame::collect::leaves;
use crate::frame::style::draw_items;
use crate::FrameSize;

/// Extra pixels around strokes and bounding boxes so thin shapes stay clickable.
const PICK_TOLERANCE_PX: f64 = 3.0;

/// Topmost present, visible leaf under pixel (`x`, `y`) (y-down, origin top-left) of a
/// frame of `size` at `t`.
///
/// First pass: exact hit on the drawn geometry (fill winding, or a stroke's inflated
/// bounds). Second pass: the object's world bounding box, so clicks between the glyphs
/// of a text still select it.
pub fn pick_object(scene: &Scene, t: f64, size: FrameSize, x: f64, y: f64) -> Option<ObjectId> {
    let evaluator = Evaluator::new(scene);
    let layout = Layout::new(&evaluator);
    pick_object_in_layout(&layout, t, size, x, y)
}

/// [`pick_object`] on an existing layout (reuses its caches).
pub fn pick_object_in_layout(layout: &Layout, t: f64, size: FrameSize, x: f64, y: f64) -> Option<ObjectId> {
    let point = Point::new(x, y);
    let topmost_first: Vec<ObjectId> = leaves(layout, t).into_iter().rev().collect();
    let drawn = |o: ObjectId| draw_items(layout, o, t, size);
    if let Some(&hit) = topmost_first.iter().find(|&&o| drawn(o).iter().any(|item| item_contains(item, point))) {
        return Some(hit);
    }
    let to_pixels = size.pixel_affine(layout.scene());
    topmost_first.into_iter().find(|&o| {
        !drawn(o).is_empty() && inflate(to_pixels.transform_rect_bbox(layout.world_bbox(o, t))).contains(point)
    })
}

fn inflate(r: Rect) -> Rect {
    r.inflate(PICK_TOLERANCE_PX, PICK_TOLERANCE_PX)
}

fn item_contains(item: &crate::raster::DrawItem, point: Point) -> bool {
    if item.opacity <= 0.0 {
        return false;
    }
    if let Some(clip) = &item.clip {
        if clip.winding(point) == 0 {
            return false;
        }
    }
    let painted_inside = item.fill.as_ref().is_some_and(|f| f.color[3] > 0.0) || item.image.is_some();
    let filled = painted_inside && item.path.winding(point) != 0;
    let stroked = item.stroke.as_ref().is_some_and(|s| {
        let half = s.width / 2.0 + PICK_TOLERANCE_PX;
        s.color[3] > 0.0 && item.path.bounding_box().inflate(half, half).contains(point)
    });
    filled || stroked
}
