//! Mass rendering: batching, reveal and the 10k-points budget.

use std::collections::BTreeMap;
use std::time::Instant;

use kinemo_ir::{Entry, Expr, Lerp, Object, Scene, SceneConfig, Signal, Span, Src, UnOp, Value};

use crate::frame::{display_list, FrameSize};
use crate::raster::rasterize;

const HD: FrameSize = FrameSize { width: 1920, height: 1080 };

fn p(attr: &str) -> Box<Expr> {
    Box::new(Expr::Point { attr: attr.into() })
}

fn scene(kind: &str, props: Vec<(&str, Value, Option<Expr>)>) -> Scene {
    let mut s = Scene::new(SceneConfig::default());
    let mut map = BTreeMap::new();
    for (name, initial, binding) in props {
        let id = s.signals.len() as u32;
        let timeline = binding.map(|e| vec![Entry::Set { t: 0.0, src: Src::Expr { e }, span: Span::default() }]).unwrap_or_default();
        s.signals.push(Signal { id, initial, lerp: Lerp::Linear, timeline, owner: Some((0, name.into())), span: Span::default() });
        map.insert(name.to_string(), id);
    }
    s.objects.push(Object { id: 0, kind: kind.into(), props: map, presence: vec![(0.0, true)], ..Default::default() });
    s.roots.push(0);
    s
}

/// `n` points on a deterministic spiral filling the frame.
fn spiral(n: usize) -> Value {
    Value::List(
        (0..n)
            .map(|i| {
                let f = i as f64 / n as f64;
                let a = i as f64 * 2.399_963;
                Value::Vec2([7.0 * f.sqrt() * a.cos(), 4.0 * f.sqrt() * a.sin()])
            })
            .collect(),
    )
}

fn gradient_points(n: usize) -> Scene {
    let blue = Expr::Const { v: Value::Color([0.2, 0.4, 1.0, 1.0]) };
    let red = Expr::Const { v: Value::Color([1.0, 0.2, 0.2, 1.0]) };
    // mix(blue, red, (x + 7) / 14)
    let t = Expr::Bin {
        f: kinemo_ir::BinOp::Div,
        a: Box::new(Expr::Bin { f: kinemo_ir::BinOp::Add, a: p("x"), b: Box::new(Expr::Const { v: Value::Float(7.0) }) }),
        b: Box::new(Expr::Const { v: Value::Float(14.0) }),
    };
    scene(
        "points",
        vec![
            ("xy", spiral(n), None),
            ("radius", Value::Float(0.02), None),
            ("color", Value::None, Some(Expr::Mix { a: Box::new(blue), b: Box::new(red), t: Box::new(t) })),
        ],
    )
}

#[test]
fn points_are_batched_per_color() {
    let s = gradient_points(10_000);
    let dl = display_list(&s, 0.0, HD, false);
    assert!(!dl.items.is_empty());
    assert!(dl.items.len() <= 1024, "{} items for one gradient", dl.items.len());
    assert!(dl.items.iter().all(|i| i.fill.is_some() && i.stroke.is_none()));
}

#[test]
fn ten_thousand_points_render_within_budget() {
    let s = gradient_points(10_000);
    // Warm up, then take the best of a few runs (CI machines are noisy).
    let _ = rasterize(&display_list(&s, 0.0, HD, false), true);
    let best = (0..3)
        .map(|_| {
            let start = Instant::now();
            let img = rasterize(&display_list(&s, 0.0, HD, false), true);
            assert_eq!(img.rgba.len(), 1920 * 1080 * 4);
            start.elapsed().as_secs_f64() * 1000.0
        })
        .fold(f64::INFINITY, f64::min);
    eprintln!("10k points @1080p: {best:.1} ms");
    // Debug builds are much slower; the budget (< 100 ms) is for optimized builds.
    let budget = if cfg!(debug_assertions) { 1000.0 } else { 100.0 };
    assert!(best < budget, "10k points took {best:.1} ms");
}

#[test]
fn draw_progress_reveals_points_in_index_order() {
    let mut s = gradient_points(100);
    let id = s.signals.len() as u32;
    s.signals.push(Signal { id, initial: Value::Float(0.5), lerp: Lerp::Linear, timeline: vec![], owner: Some((0, "_draw".into())), span: Span::default() });
    s.objects[0].props.insert("_draw".into(), id);
    let full = display_list(&gradient_points(100), 0.0, HD, false);
    let half = display_list(&s, 0.0, HD, false);
    let count = |dl: &crate::raster::DisplayList| dl.items.iter().map(|i| i.path.elements().iter().filter(|e| matches!(e, kurbo::PathEl::MoveTo(_))).count()).sum::<usize>();
    assert_eq!(count(&full), 100);
    assert_eq!(count(&half), 50);
}

#[test]
fn field_and_stream_lines_draw() {
    let rotation = Expr::Vec2 { x: Box::new(Expr::Un { f: UnOp::Neg, a: p("y") }), y: p("x") };
    let field = scene("vector_field", vec![("field", Value::Vec2([0.0, 0.0]), Some(rotation.clone())), ("density", Value::Float(20.0), None)]);
    let dl = display_list(&field, 0.0, HD, false);
    assert!(dl.items.iter().any(|i| i.stroke.is_some()) && dl.items.iter().any(|i| i.fill.is_some()));
    let lines = scene("stream_lines", vec![("field", Value::Vec2([0.0, 0.0]), Some(rotation)), ("seed_count", Value::Float(200.0), None), ("fade", Value::Float(0.1), None)]);
    let start = Instant::now();
    let dl = display_list(&lines, 0.0, HD, false);
    eprintln!("200 stream lines layout+display list: {:.1} ms", start.elapsed().as_secs_f64() * 1000.0);
    assert!(!dl.items.is_empty());
    // The fade: the faintest bucket is drawn before the opaque head.
    let alphas: Vec<f64> = dl.items.iter().map(|i| i.stroke.as_ref().unwrap().color[3]).collect();
    assert!(alphas.first() < alphas.last());
    let img = rasterize(&dl, true);
    assert!(img.rgba.chunks(4).any(|px| px[0] > 100 || px[2] > 150));
}
