//! Unit tests of the mass kinds on hand-built scenes.

use std::collections::BTreeMap;

use kinemo_eval::Evaluator;
use kinemo_ir::{BinOp, Entry, Expr, Lerp, Object, Scene, SceneConfig, Signal, Span, Src, UnOp, Value};

use super::stream_lines::halton_seeds;
use crate::Layout;

fn p(attr: &str) -> Box<Expr> {
    Box::new(Expr::Point { attr: attr.into() })
}

/// The rotation field (-y, x).
fn rotation() -> Expr {
    Expr::Vec2 { x: Box::new(Expr::Un { f: UnOp::Neg, a: p("y") }), y: p("x") }
}

/// A scene with one object of `kind` whose props are constants or per-point bindings.
fn scene(kind: &str, props: Vec<(&str, Value, Option<Expr>)>) -> Scene {
    let mut s = Scene::new(SceneConfig::default());
    let mut map = BTreeMap::new();
    for (i, (name, initial, binding)) in props.into_iter().enumerate() {
        let timeline = binding.map(|e| vec![Entry::Set { t: 0.0, src: Src::Expr { e }, span: Span::default() }]).unwrap_or_default();
        s.signals.push(Signal { id: i as u32, initial, lerp: Lerp::Linear, timeline, owner: Some((0, name.into())), span: Span::default() });
        map.insert(name.to_string(), i as u32);
    }
    s.objects.push(Object { id: 0, kind: kind.into(), props: map, presence: vec![(0.0, true)], ..Default::default() });
    s.roots.push(0);
    s
}

fn xy(points: &[[f64; 2]]) -> Value {
    Value::List(points.iter().map(|p| Value::Vec2(*p)).collect())
}

#[test]
fn points_uniform_list_and_per_point_props() {
    let gradient = Expr::Mix {
        a: Box::new(Expr::Const { v: Value::Color([0.0, 0.0, 1.0, 1.0]) }),
        b: Box::new(Expr::Const { v: Value::Color([1.0, 0.0, 0.0, 1.0]) }),
        t: p("t"),
    };
    let s = scene(
        "points",
        vec![
            ("xy", xy(&[[0.0, 0.0], [1.0, 0.0], [2.0, 1.0]]), None),
            ("radius", Value::Float(0.0), Some(Expr::Bin { f: BinOp::Mul, a: p("index"), b: Box::new(Expr::Const { v: Value::Float(0.1) }) })),
            ("color", Value::None, Some(gradient)),
        ],
    );
    let ev = Evaluator::new(&s);
    let l = Layout::new(&ev);
    let b = l.point_batch(0, 0.0);
    assert_eq!(b.len(), 3);
    assert_eq!(b.radii, vec![0.0, 0.1, 0.2]);
    assert_eq!(b.colors[0], [0.0, 0.0, 1.0, 1.0]);
    assert!((b.colors[2][0] - 1.0).abs() < 1e-9);
    let bbox = l.local_bbox(0, 0.0);
    assert!((bbox.x1 - 2.2).abs() < 1e-9 && (bbox.y1 - 1.2).abs() < 1e-9);

    let s = scene("points", vec![("xy", xy(&[[0.0, 0.0], [1.0, 0.0]]), None), ("radius", Value::List(vec![Value::Float(0.3), Value::Float(0.5)]), None)]);
    let ev = Evaluator::new(&s);
    assert_eq!(Layout::new(&ev).point_batch(0, 0.0).radii, vec![0.3, 0.5]);
}

#[test]
fn vector_field_grid_scales_and_colors_by_magnitude() {
    let s = scene(
        "vector_field",
        vec![
            ("field", Value::Vec2([0.0, 0.0]), Some(rotation())),
            ("density", Value::Float(4.0), None),
            ("x_range", Value::Vec2([-2.0, 2.0]), None),
            ("y_range", Value::Vec2([-2.0, 2.0]), None),
            ("length", Value::Float(1.0), None),
        ],
    );
    let ev = Evaluator::new(&s);
    let l = Layout::new(&ev);
    let arrows = l.field_arrows(0, 0.0);
    assert_eq!(arrows.len(), 16);
    // Corner cells are the strongest (|v| = |p|): full cell length, the high color.
    let strongest = arrows.iter().max_by(|a, b| a.magnitude.total_cmp(&b.magnitude)).unwrap();
    assert!((strongest.magnitude - 1.0).abs() < 1e-9);
    let len = (strongest.end[0] - strongest.start[0]).hypot(strongest.end[1] - strongest.start[1]);
    assert!((len - 1.0).abs() < 1e-9);
    // Rotation: arrows are perpendicular to the position.
    for a in &arrows {
        let c = [(a.start[0] + a.end[0]) / 2.0, (a.start[1] + a.end[1]) / 2.0];
        let d = [a.end[0] - a.start[0], a.end[1] - a.start[1]];
        assert!((c[0] * d[0] + c[1] * d[1]).abs() < 1e-9);
    }
}

#[test]
fn stream_lines_follow_circles_of_the_rotation_field() {
    let s = scene(
        "stream_lines",
        vec![
            ("field", Value::Vec2([0.0, 0.0]), Some(rotation())),
            ("seeds", xy(&[[1.0, 0.0], [2.0, 0.0]]), None),
            ("step", Value::Float(0.05), None),
            ("steps", Value::Float(100.0), None),
        ],
    );
    let ev = Evaluator::new(&s);
    let l = Layout::new(&ev);
    let lines = l.stream_lines(0, 0.0);
    assert_eq!(lines.len(), 2);
    for (line, r) in lines.iter().zip([1.0, 2.0]) {
        assert_eq!(line.points.len(), 101);
        for q in &line.points {
            assert!((q[0].hypot(q[1]) - r).abs() < 1e-5, "RK4 drifted off the circle: {q:?}");
        }
        let total = *line.cumulative_lengths().last().unwrap();
        assert!((total - 5.0).abs() < 1e-3);
    }
    // Counter-clockwise from (1, 0): the first step goes up.
    assert!(lines[0].points[1][1] > 0.0);
    // Deterministic: a second layout gives the same lines.
    let again = Layout::new(&ev).stream_lines(0, 0.0);
    assert_eq!(lines, again);
}

#[test]
fn stream_lines_seed_count_uses_halton_points_in_the_region() {
    let region = kurbo::Rect::new(-1.0, -1.0, 1.0, 1.0);
    let seeds = halton_seeds(region, 50);
    assert_eq!(seeds.len(), 50);
    assert!(seeds.iter().all(|s| region.contains(kurbo::Point::new(s[0], s[1]))));
    assert!(seeds[0][0].abs() < 1e-12 && (seeds[0][1] + 1.0 / 3.0).abs() < 1e-12);
    let s = scene("stream_lines", vec![("field", Value::Vec2([1.0, 0.0]), None), ("seed_count", Value::Float(12.0), None)]);
    let ev = Evaluator::new(&s);
    let lines = Layout::new(&ev).stream_lines(0, 0.0);
    assert_eq!(lines.len(), 12);
    // A uniform field to the right: lines are horizontal.
    assert!(lines.iter().all(|l| l.points.iter().all(|q| (q[1] - l.points[0][1]).abs() < 1e-12)));
}
