use kurbo::{BezPath, ParamCurve, ParamCurveArclen, PathEl, PathSeg, Point};

use super::ARCLEN_ACCURACY;

/// One drawable segment of a path, tagged with the subpath it belongs to.
struct Piece {
    seg: PathSeg,
    len: f64,
    subpath: usize,
    /// Implicit segment produced by a `ClosePath`.
    closing: bool,
}

/// Flatten the path's elements into segments, remembering subpath boundaries
/// and which subpaths were closed.
fn pieces(p: &BezPath) -> (Vec<Piece>, Vec<bool>) {
    let mut out = Vec::new();
    let mut closed = Vec::new();
    let mut start = Point::ZERO;
    let mut cur = Point::ZERO;
    let mut sub: Option<usize> = None;
    let push = |seg: PathSeg, sub: usize, closing: bool, out: &mut Vec<Piece>| {
        let len = seg.arclen(ARCLEN_ACCURACY);
        out.push(Piece { seg, len, subpath: sub, closing });
    };
    for el in p.elements() {
        // Drawing commands without a preceding move_to start an implicit subpath.
        if !matches!(el, PathEl::MoveTo(_)) && sub.is_none() {
            sub = Some(closed.len());
            closed.push(false);
        }
        match *el {
            PathEl::MoveTo(pt) => {
                sub = Some(closed.len());
                closed.push(false);
                start = pt;
                cur = pt;
            }
            PathEl::LineTo(pt) => {
                push(PathSeg::Line(kurbo::Line::new(cur, pt)), sub.unwrap(), false, &mut out);
                cur = pt;
            }
            PathEl::QuadTo(a, b) => {
                push(PathSeg::Quad(kurbo::QuadBez::new(cur, a, b)), sub.unwrap(), false, &mut out);
                cur = b;
            }
            PathEl::CurveTo(a, b, c) => {
                let seg = PathSeg::Cubic(kurbo::CubicBez::new(cur, a, b, c));
                push(seg, sub.unwrap(), false, &mut out);
                cur = c;
            }
            PathEl::ClosePath => {
                let s = sub.unwrap();
                closed[s] = true;
                if cur != start {
                    push(PathSeg::Line(kurbo::Line::new(cur, start)), s, true, &mut out);
                }
                cur = start;
                // A subsequent drawing command continues from `start` in a new subpath.
                sub = None;
            }
        }
    }
    (out, closed)
}

fn append_seg(out: &mut BezPath, seg: PathSeg) {
    match seg {
        PathSeg::Line(l) => out.line_to(l.p1),
        PathSeg::Quad(q) => out.quad_to(q.p1, q.p2),
        PathSeg::Cubic(c) => out.curve_to(c.p1, c.p2, c.p3),
    }
}

/// Portion of the path between arc-length fractions `[start, end]` of the
/// whole path (subpaths concatenated in order). Curves are preserved via
/// segment subdivision. `start >= end` yields an empty path.
pub fn trim(p: &BezPath, start: f64, end: f64) -> BezPath {
    let start = start.clamp(0.0, 1.0);
    let end = end.clamp(0.0, 1.0);
    let mut out = BezPath::new();
    if start >= end {
        return out;
    }
    let (pieces, closed) = pieces(p);
    let total: f64 = pieces.iter().map(|pc| pc.len).sum();
    if total <= 0.0 {
        return out;
    }
    if start <= 0.0 && end >= 1.0 {
        return p.clone();
    }
    let (s_len, e_len) = (start * total, end * total);

    let mut acc = 0.0;
    let mut cur_sub: Option<usize> = None;
    // Whether the subpath currently being emitted has been included from its
    // very first segment (needed to emit a proper ClosePath).
    let mut sub_from_start = false;
    let mut sub_first_piece = true;
    let mut prev_sub: Option<usize> = None;
    for (i, pc) in pieces.iter().enumerate() {
        if prev_sub != Some(pc.subpath) {
            sub_first_piece = true;
            prev_sub = Some(pc.subpath);
        }
        let (a, b) = (acc, acc + pc.len);
        acc = b;
        let first_in_sub = std::mem::replace(&mut sub_first_piece, false);
        if b <= s_len || a >= e_len || pc.len <= 0.0 {
            continue;
        }
        let t0 = if s_len > a {
            pc.seg.inv_arclen(s_len - a, ARCLEN_ACCURACY)
        } else {
            0.0
        };
        let t1 = if e_len < b {
            pc.seg.inv_arclen(e_len - a, ARCLEN_ACCURACY)
        } else {
            1.0
        };
        if t1 <= t0 {
            continue;
        }
        let sub_seg = if t0 == 0.0 && t1 == 1.0 { pc.seg } else { pc.seg.subsegment(t0..t1) };
        if cur_sub != Some(pc.subpath) {
            out.move_to(sub_seg.start());
            cur_sub = Some(pc.subpath);
            sub_from_start = first_in_sub && t0 == 0.0;
        }
        let whole_closing = pc.closing && t1 == 1.0 && sub_from_start;
        if whole_closing {
            out.close_path();
        } else {
            append_seg(&mut out, sub_seg);
            // A closed subpath with no explicit closing segment (end == start).
            let last_of_closed = closed[pc.subpath] && t1 == 1.0 && sub_from_start && !pc.closing;
            let last_in_sub = pieces.get(i + 1).is_none_or(|n| n.subpath != pc.subpath);
            if last_of_closed && last_in_sub {
                out.close_path();
            }
        }
    }
    out
}
