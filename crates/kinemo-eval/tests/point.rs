//! Per-point evaluation (`Expr::Point`, `PointContext`) for mass objects.

mod common;

use common::*;
use kinemo_eval::{Evaluator, NoResolver, PointContext};
use kinemo_ir::{BinOp, Expr, Value};

const R: NoResolver = NoResolver;

fn p(attr: &str) -> Expr {
    Expr::Point { attr: attr.into() }
}

fn color(c: [f64; 4]) -> Expr {
    konst(Value::Color(c))
}

#[test]
fn point_attributes() {
    let s = scene(vec![]);
    let ev = Evaluator::new(&s);
    let pt = PointContext::new(1.5, -2.0, 3, 7);
    assert_eq!(ev.expr_at_point(&p("x"), 0.0, &R, &pt), float(1.5));
    assert_eq!(ev.expr_at_point(&p("y"), 0.0, &R, &pt), float(-2.0));
    assert_eq!(ev.expr_at_point(&p("index"), 0.0, &R, &pt), float(3.0));
    assert_eq!(ev.expr_at_point(&p("count"), 0.0, &R, &pt), float(7.0));
    assert_eq!(ev.expr_at_point(&p("t"), 0.0, &R, &pt), float(0.5));
    assert_eq!(PointContext::new(0.0, 0.0, 0, 1).param(), 0.0);
}

#[test]
fn point_reads_are_zero_without_a_context() {
    let s = scene(vec![]);
    let ev = Evaluator::new(&s);
    assert_eq!(ev.expr(&p("x"), 0.0, &R), float(0.0));
}

#[test]
fn per_point_expression_mixes_time_signals_and_point() {
    // x * time + sig0
    let s = scene(vec![num(10.0, vec![])]);
    let ev = Evaluator::new(&s);
    let e = bin(BinOp::Add, bin(BinOp::Mul, p("x"), Expr::Time), sig(0));
    let pt = PointContext::new(2.0, 0.0, 0, 1);
    assert_eq!(ev.expr_at_point(&e, 3.0, &R, &pt), float(16.0));
    // field (-y, x)
    let f = Expr::Vec2 { x: Box::new(Expr::Un { f: kinemo_ir::UnOp::Neg, a: Box::new(p("y")) }), y: Box::new(p("x")) };
    assert_eq!(ev.expr_at_point(&f, 0.0, &R, &PointContext::new(1.0, 2.0, 0, 1)), Value::Vec2([-2.0, 1.0]));
}

#[test]
fn signal_at_point_follows_bindings_and_animations() {
    let blue = [0.0, 0.0, 1.0, 1.0];
    let red = [1.0, 0.0, 0.0, 1.0];
    let gradient = Expr::Mix { a: Box::new(color(blue)), b: Box::new(color(red)), t: Box::new(p("x")) };
    let s = scene(vec![
        num(0.0, vec![set(0.0, ex(bin(BinOp::Mul, p("index"), konst(float(2.0)))))]),
        signal(Value::Color(blue), kinemo_ir::Lerp::Linear, vec![set(0.0, ex(gradient)), anim(1.0, 2.0, val(Value::Color(red)))]),
        num(4.0, vec![]),
    ]);
    let ev = Evaluator::new(&s);
    assert!(ev.signal_uses_point(0) && ev.signal_uses_point(1) && !ev.signal_uses_point(2));
    let pt = PointContext::new(0.0, 0.0, 5, 10);
    assert_eq!(ev.signal_at_point(0, 0.5, &R, &pt), float(10.0));
    assert_eq!(ev.signal_at_point(2, 0.5, &R, &pt), float(4.0));
    // Before the animation: the per-point gradient (x = 0 → blue, x = 1 → red).
    assert_eq!(ev.signal_at_point(1, 0.5, &R, &pt), Value::Color(blue));
    let Value::Color(c) = ev.signal_at_point(1, 0.5, &R, &PointContext::new(1.0, 0.0, 0, 1)) else { panic!() };
    assert!((c[0] - 1.0).abs() < 1e-9 && c[2].abs() < 1e-9);
    // Halfway through the animation to solid red, a blue point is between the two.
    let Value::Color(c) = ev.signal_at_point(1, 1.5, &R, &pt) else { panic!() };
    assert!(c[0] > 0.1 && c[2] > 0.1, "{c:?}");
    // After it every point is red.
    assert_eq!(ev.signal_at_point(1, 2.5, &R, &pt), Value::Color(red));
}
