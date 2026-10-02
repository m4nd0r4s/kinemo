use kurbo::Point;

/// Resample a polyline into `n` points spaced uniformly by arc length.
/// The first and last output points coincide with the polyline endpoints.
pub fn resample_points(pts: &[Point], n: usize) -> Vec<Point> {
    if n == 0 || pts.is_empty() {
        return Vec::new();
    }
    if n == 1 || pts.len() == 1 {
        return vec![pts[0]; n];
    }
    // Cumulative lengths.
    let mut cum = Vec::with_capacity(pts.len());
    cum.push(0.0);
    for w in pts.windows(2) {
        let last = *cum.last().unwrap();
        cum.push(last + w[0].distance(w[1]));
    }
    let total = *cum.last().unwrap();
    if total <= 0.0 {
        return vec![pts[0]; n];
    }
    let mut out = Vec::with_capacity(n);
    let mut seg = 0usize;
    for i in 0..n {
        if i == n - 1 {
            out.push(*pts.last().unwrap());
            break;
        }
        let target = total * i as f64 / (n - 1) as f64;
        while seg + 2 < cum.len() && cum[seg + 1] < target {
            seg += 1;
        }
        let len = cum[seg + 1] - cum[seg];
        let t = if len > 0.0 { ((target - cum[seg]) / len).clamp(0.0, 1.0) } else { 0.0 };
        out.push(pts[seg].lerp(pts[seg + 1], t));
    }
    out
}
