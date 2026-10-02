//! `vector_field` arrows and `stream_lines` polylines, merged per color.

use kurbo::{BezPath, Point};

use kinemo_layout::mass::StreamLine;

use super::{Buckets, MassContext};
use crate::raster::{Cap, DrawItem};

/// Arrow head length as a fraction of the arrow, and its half-width relative to it.
const TIP_FRACTION: f64 = 0.35;
const TIP_HALF_WIDTH: f64 = 0.5;
/// Opacity steps of a stream line's fading tail.
const FADE_STEPS: u32 = 8;

/// Arrows: shafts stroked, heads filled; `k.draw` grows every arrow from its start.
pub(super) fn arrows(cx: &MassContext) -> Vec<DrawItem> {
    let (l, o, t) = (cx.layout, cx.leaf, cx.t);
    let width = l.prop_f(o, "stroke_width", t, 2.5) * cx.stroke_scale;
    let mut shafts = Buckets::default();
    let mut heads = Buckets::default();
    for a in l.field_arrows(o, t) {
        let start = Point::new(a.start[0], a.start[1]);
        let d = (Point::new(a.end[0], a.end[1]) - start) * cx.progress;
        let len = d.hypot();
        if len <= 0.0 {
            continue;
        }
        let color = cx.tinted(a.color);
        let end = start + d;
        let dir = d / len;
        let normal = kurbo::Vec2::new(-dir.y, dir.x);
        let tip = len * TIP_FRACTION;
        let base = end - dir * tip;
        let shaft = shafts.path(0, color);
        shaft.move_to(cx.to_px * start);
        shaft.line_to(cx.to_px * base);
        let head = heads.path(0, color);
        head.move_to(cx.to_px * end);
        head.line_to(cx.to_px * (base + normal * (tip * TIP_HALF_WIDTH)));
        head.line_to(cx.to_px * (base - normal * (tip * TIP_HALF_WIDTH)));
        head.close_path();
    }
    let mut items = shafts.into_strokes(width, Cap::Butt);
    items.extend(heads.into_fills());
    items
}

/// Stream lines: the visible window of each line ends at `progress · length` (times
/// the `k.draw` progress) and spans `tail · length` behind it; its opacity rises from
/// `fade` at the tail end to 1 at the head, in [`FADE_STEPS`] steps.
pub(super) fn lines(cx: &MassContext) -> Vec<DrawItem> {
    let (l, o, t) = (cx.layout, cx.leaf, cx.t);
    let width = l.prop_f(o, "stroke_width", t, 2.0) * cx.stroke_scale;
    let progress = l.prop_f(o, "progress", t, 1.0).clamp(0.0, 1.0) * cx.progress;
    let tail = l.prop_f(o, "tail", t, 1.0).clamp(0.0, 1.0);
    let fade = l.prop_f(o, "fade", t, 0.0).clamp(0.0, 1.0);
    let mut buckets = Buckets::default();
    for line in l.stream_lines(o, t) {
        let lengths = line.cumulative_lengths();
        let total = *lengths.last().unwrap_or(&0.0);
        if total <= 0.0 {
            continue;
        }
        let head = progress * total;
        let start = (head - tail * total).max(0.0);
        if head <= start {
            continue;
        }
        let color = cx.tinted(line.color);
        for k in 0..FADE_STEPS {
            let a = start + (head - start) * k as f64 / FADE_STEPS as f64;
            let b = start + (head - start) * (k + 1) as f64 / FADE_STEPS as f64;
            let alpha = fade + (1.0 - fade) * (k + 1) as f64 / FADE_STEPS as f64;
            let c = [color[0], color[1], color[2], color[3] * alpha];
            push_window(buckets.path(k, c), cx, &line, &lengths, a, b);
        }
    }
    buckets.into_strokes(width, Cap::Butt)
}

/// Appends the part of `line` between arc lengths `a` and `b` (pixels) to `path`.
fn push_window(path: &mut BezPath, cx: &MassContext, line: &StreamLine, lengths: &[f64], a: f64, b: f64) {
    let at = |s: f64| -> Point {
        let i = lengths.partition_point(|&v| v < s).clamp(1, lengths.len() - 1);
        let (s0, s1) = (lengths[i - 1], lengths[i]);
        let (p, q) = (line.points[i - 1], line.points[i]);
        let u = if s1 > s0 { ((s - s0) / (s1 - s0)).clamp(0.0, 1.0) } else { 0.0 };
        Point::new(p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
    };
    if line.points.len() < 2 {
        return;
    }
    path.move_to(cx.to_px * at(a));
    for (i, &s) in lengths.iter().enumerate() {
        if s > a && s < b {
            let p = line.points[i];
            path.line_to(cx.to_px * Point::new(p[0], p[1]));
        }
    }
    path.line_to(cx.to_px * at(b));
}
