use super::*;
use kurbo::{BezPath, Circle, ParamCurve, Point, Rect, Shape};

fn square() -> BezPath {
    Rect::new(0.0, 0.0, 10.0, 10.0).to_path(0.1)
}

#[test]
fn length_of_square_and_circle() {
    assert!((path_length(&square()) - 40.0).abs() < 1e-6);
    let c = Circle::new((0.0, 0.0), 10.0).to_path(1e-6);
    assert!((path_length(&c) - 20.0 * std::f64::consts::PI).abs() < 1e-3);
}

#[test]
fn trim_half_has_half_length() {
    for p in [square(), Circle::new((5.0, 5.0), 7.0).to_path(1e-6)] {
        let total = path_length(&p);
        let h = trim(&p, 0.0, 0.5);
        assert!((path_length(&h) - total / 2.0).abs() < 1e-3, "{}", path_length(&h));
        let mid = trim(&p, 0.25, 0.75);
        assert!((path_length(&mid) - total / 2.0).abs() < 1e-3);
    }
}

#[test]
fn trim_preserves_curves() {
    let c = Circle::new((0.0, 0.0), 10.0).to_path(1e-6);
    let h = trim(&c, 0.1, 0.6);
    assert!(h.elements().iter().any(|e| matches!(e, kurbo::PathEl::CurveTo(..))));
}

#[test]
fn trim_square_endpoints() {
    let h = trim(&square(), 0.0, 0.5);
    let segs: Vec<_> = h.segments().collect();
    assert_eq!(segs.len(), 2);
    assert_eq!(segs[1].end(), Point::new(10.0, 10.0));
}

#[test]
fn trim_empty_and_full() {
    assert!(trim(&square(), 0.5, 0.5).elements().is_empty());
    assert!(trim(&square(), 0.7, 0.2).elements().is_empty());
    assert_eq!(trim(&square(), 0.0, 1.0), square());
}

#[test]
fn trim_multiple_subpaths() {
    let mut p = BezPath::new();
    p.move_to((0.0, 0.0));
    p.line_to((10.0, 0.0));
    p.move_to((0.0, 5.0));
    p.line_to((30.0, 5.0));
    // total 40; [0.125, 0.5] => 5..20 => 5 on first, 10 on second
    let t = trim(&p, 0.125, 0.5);
    let move_count = t.elements().iter().filter(|e| matches!(e, kurbo::PathEl::MoveTo(_))).count();
    assert_eq!(move_count, 2);
    assert!((path_length(&t) - 15.0).abs() < 1e-9);
}

#[test]
fn bbox_works() {
    assert_eq!(bbox(&square()), Some(Rect::new(0.0, 0.0, 10.0, 10.0)));
    assert_eq!(bbox(&BezPath::new()), None);
    let c = Circle::new((5.0, 5.0), 2.0).to_path(1e-6);
    let b = bbox(&c).unwrap();
    assert!((b.x0 - 3.0).abs() < 1e-6 && (b.x1 - 7.0).abs() < 1e-6);
}

#[test]
fn resample_uniform() {
    let pts = [Point::new(0.0, 0.0), Point::new(10.0, 0.0), Point::new(10.0, 10.0)];
    let r = resample_points(&pts, 5);
    let expected = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 5.0), (10.0, 10.0)];
    assert_eq!(r.len(), 5);
    for (a, b) in r.iter().zip(expected) {
        assert!(a.distance(Point::new(b.0, b.1)) < 1e-9, "{a:?} vs {b:?}");
    }
    assert!(resample_points(&pts, 0).is_empty());
    assert_eq!(resample_points(&pts, 1), vec![pts[0]]);
}
