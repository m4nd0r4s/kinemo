//! Morphs: the parts of one subtree travel into the parts of another.
//!
//! Paired parts interpolate their outlines (subpath by subpath, resampled by arc length,
//! with the start point of closed contours aligned) and their styles; unpaired parts
//! fade out (source) or in (target).

use kurbo::{BezPath, PathEl, Point, Shape};

use kinemo_eval::color;
use kinemo_ir::{ObjectId, Value};
use kinemo_layout::Layout;

use super::style::{painted_parts, PaintedPart, Reveal};
use super::FrameSize;
use crate::geom::resample_points;
use crate::raster::{DrawItem, Fill, ImagePaint, Stroke};

const SAMPLES: usize = 72;

/// Painted parts of a subtree in draw order (pixel space), with the leaf each came from.
pub(crate) fn subtree_parts(layout: &Layout, root: ObjectId, t: f64, size: FrameSize) -> Vec<(ObjectId, PaintedPart)> {
    let mut out = Vec::new();
    let mut stack = vec![root];
    while let Some(o) = stack.pop() {
        if layout.scene().object(o).children.is_some() {
            stack.extend(layout.children(o, t).into_iter().rev());
        } else {
            out.extend(painted_parts(layout, o, t, size, Reveal::Full).into_iter().map(|p| (o, p)));
        }
    }
    out
}

fn object_prop(layout: &Layout, o: ObjectId, name: &str, t: f64) -> Option<ObjectId> {
    match layout.prop(o, name, t)? {
        Value::Object(id) => Some(id),
        _ => None,
    }
}

pub(crate) fn draw_items(layout: &Layout, morph: ObjectId, t: f64, size: FrameSize) -> Vec<DrawItem> {
    let (Some(a), Some(b)) = (object_prop(layout, morph, "a", t), object_prop(layout, morph, "b", t)) else {
        return vec![];
    };
    let p = layout.prop_f(morph, "progress", t, 0.0);
    let from = subtree_parts(layout, a, t, size);
    let to = subtree_parts(layout, b, t, size);
    let pairs: Vec<(usize, usize)> = layout
        .prop(morph, "pairs", t)
        .map(|v| v.as_list().iter().map(|x| { let [i, j] = x.as_v2(); (i as usize, j as usize) }).collect())
        .unwrap_or_default();
    let mut used_a = vec![false; from.len()];
    let mut used_b = vec![false; to.len()];
    let mut items = Vec::new();
    for &(i, j) in &pairs {
        let (Some((_, ia)), Some((_, ib))) = (from.get(i), to.get(j)) else { continue };
        used_a[i] = true;
        used_b[j] = true;
        items.extend(blend_items(&ia.item, &ib.item, p));
    }
    for (i, (_, part)) in from.iter().enumerate() {
        if !used_a[i] {
            items.push(DrawItem { opacity: part.item.opacity * (1.0 - p), ..part.item.clone() });
        }
    }
    for (j, (_, part)) in to.iter().enumerate() {
        if !used_b[j] {
            items.push(DrawItem { opacity: part.item.opacity * p, ..part.item.clone() });
        }
    }
    items
}

/// A paired part in between: the blended outline, plus a cross-fade of the images of
/// image parts (each carried along by the outline's box, exact at its own end).
fn blend_items(a: &DrawItem, b: &DrawItem, p: f64) -> Vec<DrawItem> {
    if a.image.is_none() && b.image.is_none() {
        return vec![blend_shapes(a, b, p)];
    }
    // An image blends as a transparent rectangle of its mean color.
    let as_shape = |item: &DrawItem| match &item.image {
        Some(img) => {
            let [r, g, b, _] = img.bitmap.average_color;
            DrawItem { fill: Some(Fill { color: [r, g, b, 0.0] }), image: None, ..item.clone() }
        }
        None => item.clone(),
    };
    let shape = blend_shapes(&as_shape(a), &as_shape(b), p);
    let bounds = shape.path.bounding_box();
    let mut out = vec![shape.clone()];
    for (side, weight) in [(a, 1.0 - p), (b, p)] {
        let Some(img) = &side.image else { continue };
        let from = side.path.bounding_box();
        let carry = rect_to_rect(from, bounds);
        out.push(DrawItem {
            path: shape.path.clone(),
            fill: None,
            stroke: None,
            opacity: side.opacity * weight,
            clip: side.clip.clone(),
            fill_rule_even_odd: false,
            image: Some(ImagePaint { bitmap: img.bitmap.clone(), transform: carry * img.transform }),
            dots: None, glow: None,
        });
    }
    out
}

/// Scale + translation taking rectangle `from` onto `to`.
fn rect_to_rect(from: kurbo::Rect, to: kurbo::Rect) -> kurbo::Affine {
    let sx = if from.width() > 1e-9 { to.width() / from.width() } else { 1.0 };
    let sy = if from.height() > 1e-9 { to.height() / from.height() } else { 1.0 };
    kurbo::Affine::new([sx, 0.0, 0.0, sy, to.x0 - from.x0 * sx, to.y0 - from.y0 * sy])
}

fn blend_shapes(a: &DrawItem, b: &DrawItem, p: f64) -> DrawItem {
    let mix = |x: [f64; 4], y: [f64; 4]| color::mix(x, y, p);
    let transparent = |c: [f64; 4]| [c[0], c[1], c[2], 0.0];
    let fill = match (&a.fill, &b.fill) {
        (Some(x), Some(y)) => Some(Fill { color: mix(x.color, y.color) }),
        (Some(x), None) => Some(Fill { color: mix(x.color, transparent(x.color)) }),
        (None, Some(y)) => Some(Fill { color: mix(transparent(y.color), y.color) }),
        (None, None) => None,
    };
    let stroke = match (&a.stroke, &b.stroke) {
        (Some(x), Some(y)) => Some(Stroke { color: mix(x.color, y.color), width: x.width + (y.width - x.width) * p, ..y.clone() }),
        (Some(x), None) => Some(Stroke { color: mix(x.color, transparent(x.color)), ..x.clone() }),
        (None, Some(y)) => Some(Stroke { color: mix(transparent(y.color), y.color), ..y.clone() }),
        (None, None) => None,
    };
    DrawItem {
        path: blend_paths(&a.path, &b.path, p),
        fill,
        stroke,
        opacity: a.opacity + (b.opacity - a.opacity) * p,
        clip: None,
        fill_rule_even_odd: false,
        image: None,
        dots: None, glow: None,
    }
}

struct Contour {
    points: Vec<Point>,
    closed: bool,
}

fn contours(path: &BezPath) -> Vec<Contour> {
    let mut out: Vec<Contour> = Vec::new();
    kurbo::flatten(path, 0.25, |el| match el {
        PathEl::MoveTo(p) => out.push(Contour { points: vec![p], closed: false }),
        PathEl::LineTo(p) => {
            if let Some(c) = out.last_mut() {
                c.points.push(p);
            }
        }
        PathEl::ClosePath => {
            if let Some(c) = out.last_mut() {
                c.closed = true;
                if let Some(first) = c.points.first().copied() {
                    c.points.push(first);
                }
            }
        }
        _ => {}
    });
    out.into_iter().filter(|c| c.points.len() > 1).collect()
}

fn centroid(points: &[Point]) -> Point {
    let n = points.len().max(1) as f64;
    let (x, y) = points.iter().fold((0.0, 0.0), |(x, y), p| (x + p.x, y + p.y));
    Point::new(x / n, y / n)
}

/// Twice the signed area of a closed polygon (positive when counter-clockwise).
fn signed_area(points: &[Point]) -> f64 {
    points.iter().zip(points.iter().cycle().skip(1)).map(|(a, b)| a.x * b.y - b.x * a.y).sum()
}

/// Rotation of a closed contour's samples that best lines up with `reference`, traversed
/// in the same direction (a contour blended against its reverse folds onto itself: a
/// thin bar would vanish halfway).
fn aligned(reference: &[Point], points: Vec<Point>) -> Vec<Point> {
    let n = points.len();
    let cost = |shift: usize, pts: &[Point]| -> f64 {
        (0..n).step_by(4).map(|i| reference[i].distance_squared(pts[(i + shift) % n])).sum()
    };
    let same_direction = signed_area(reference) * signed_area(&points) >= 0.0;
    let source: Vec<Point> = if same_direction { points } else { points.iter().rev().copied().collect() };
    let shift = (0..n).min_by(|&x, &y| cost(x, &source).total_cmp(&cost(y, &source))).unwrap_or(0);
    (0..n).map(|i| source[(i + shift) % n]).collect()
}

fn blend_paths(a: &BezPath, b: &BezPath, p: f64) -> BezPath {
    let ca = contours(a);
    let cb = contours(b);
    let mut out = BezPath::new();
    for k in 0..ca.len().max(cb.len()) {
        let (pa, pb, closed) = match (ca.get(k), cb.get(k)) {
            (Some(x), Some(y)) => {
                let pa = resample_points(&x.points, SAMPLES);
                let mut pb = resample_points(&y.points, SAMPLES);
                if x.closed && y.closed {
                    pb = aligned(&pa, pb);
                }
                (pa, pb, x.closed && y.closed)
            }
            // A contour without a partner shrinks to (or grows from) its own center.
            (Some(x), None) => {
                let pa = resample_points(&x.points, SAMPLES);
                let c = centroid(&pa);
                (pa, vec![c; SAMPLES], x.closed)
            }
            (None, Some(y)) => {
                let pb = resample_points(&y.points, SAMPLES);
                let c = centroid(&pb);
                (vec![c; SAMPLES], pb, y.closed)
            }
            (None, None) => continue,
        };
        for (i, (u, v)) in pa.iter().zip(&pb).enumerate() {
            let q = u.lerp(*v, p);
            if i == 0 {
                out.move_to(q);
            } else {
                out.line_to(q);
            }
        }
        if closed {
            out.close_path();
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use kurbo::{Rect, Shape};

    #[test]
    fn endpoints_reproduce_the_shapes() {
        let a = Rect::new(0.0, 0.0, 10.0, 10.0).to_path(0.1);
        let b = Rect::new(20.0, 0.0, 30.0, 10.0).to_path(0.1);
        let start = blend_paths(&a, &b, 0.0).bounding_box();
        let end = blend_paths(&a, &b, 1.0).bounding_box();
        assert!((start.x0 - 0.0).abs() < 1e-6 && (end.x0 - 20.0).abs() < 1e-6);
    }

    #[test]
    fn a_thin_bar_keeps_its_area_halfway() {
        let a = Rect::new(0.0, 0.0, 100.0, 1.0).to_path(0.1);
        let b = Rect::new(10.0, 0.0, 120.0, 1.0).to_path(0.1);
        let mid = blend_paths(&a, &b, 0.5);
        assert!(mid.area().abs() > 50.0, "area {}", mid.area());
    }

    #[test]
    fn unpartnered_contour_collapses() {
        let a = Rect::new(0.0, 0.0, 10.0, 10.0).to_path(0.1);
        let b = BezPath::new();
        let mid = blend_paths(&a, &b, 1.0).bounding_box();
        assert!(mid.width() < 1e-6);
    }
}
