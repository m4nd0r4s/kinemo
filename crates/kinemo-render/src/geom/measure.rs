use kurbo::{BezPath, ParamCurveArclen, PathEl, Point, Rect, Shape};

use super::ARCLEN_ACCURACY;

/// Total arc length of all subpaths (closing segments included).
pub fn path_length(p: &BezPath) -> f64 {
    p.segments().map(|s| s.arclen(ARCLEN_ACCURACY)).sum()
}

/// Tight bounding box of the path, or `None` when the path has no points.
pub fn bbox(p: &BezPath) -> Option<Rect> {
    let has_points = p.elements().iter().any(|el| !matches!(el, PathEl::ClosePath));
    if !has_points {
        return None;
    }
    if p.segments().next().is_none() {
        // Only isolated move_to points: bound them directly.
        let pts: Vec<Point> = p
            .elements()
            .iter()
            .filter_map(|el| match el {
                PathEl::MoveTo(pt) => Some(*pt),
                _ => None,
            })
            .collect();
        let first = Rect::from_points(pts[0], pts[0]);
        return Some(pts.iter().fold(first, |r, pt| r.union_pt(*pt)));
    }
    Some(p.bounding_box())
}
