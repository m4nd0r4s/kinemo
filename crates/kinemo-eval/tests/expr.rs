//! Expression evaluation.

mod common;

use common::*;
use kinemo_eval::{color, noise, Evaluator, NoResolver};
use kinemo_ir::{BinOp, Expr, Table, UnOp, Value};

const R: NoResolver = NoResolver;

fn b(e: Expr) -> Box<Expr> {
    Box::new(e)
}

fn eval(e: &Expr, t: f64) -> Value {
    let s = scene(vec![]);
    Evaluator::new(&s).expr(e, t, &R)
}

fn c(v: f64) -> Expr {
    konst(float(v))
}

#[test]
fn constants_time_and_arithmetic() {
    assert_eq!(eval(&c(2.0), 0.0), float(2.0));
    assert_eq!(eval(&Expr::Time, 3.5), float(3.5));
    let e = bin(BinOp::Add, bin(BinOp::Mul, Expr::Time, c(90.0)), c(1.0));
    assert_eq!(eval(&e, 2.0), float(181.0));
    let e = Expr::Un { f: UnOp::Sin, a: b(c(0.0)) };
    assert_eq!(eval(&e, 0.0), float(0.0));
}

#[test]
fn vector_ops() {
    let v = Expr::Vec2 { x: b(c(1.0)), y: b(Expr::Time) };
    assert_eq!(eval(&v, 2.0), Value::Vec2([1.0, 2.0]));
    let scaled = bin(BinOp::Mul, v.clone(), c(3.0));
    assert_eq!(eval(&scaled, 2.0), Value::Vec2([3.0, 6.0]));
    let len = Expr::Un { f: UnOp::Len, a: b(Expr::Vec2 { x: b(c(3.0)), y: b(c(4.0)) }) };
    assert_eq!(eval(&len, 0.0), float(5.0));
    assert_eq!(eval(&Expr::Un { f: UnOp::Y, a: b(v) }, 7.0), float(7.0));
}

#[test]
fn comparisons_and_where() {
    let cond = bin(BinOp::And, bin(BinOp::Ge, Expr::Time, c(18.0)), bin(BinOp::Lt, Expr::Time, c(21.0)));
    let tarifa = Expr::Where { c: b(cond), a: b(c(1.8)), b: b(c(0.6)) };
    assert_eq!(eval(&tarifa, 17.0), float(0.6));
    assert_eq!(eval(&tarifa, 19.0), float(1.8));
    assert_eq!(eval(&tarifa, 21.0), float(0.6));
    assert_eq!(eval(&bin(BinOp::Eq, c(1.0), konst(Value::Int(1))), 0.0), Value::Bool(true));
}

#[test]
fn string_concat_and_format() {
    let e = bin(BinOp::Add, konst(Value::Str("a".into())), konst(Value::Str("b".into())));
    assert_eq!(eval(&e, 0.0), Value::Str("ab".into()));
    let fmt = Expr::Format { spec: ".2f".into(), a: b(Expr::Time) };
    let label = Expr::Concat { parts: vec![fmt, konst(Value::Str(" kWh".into()))] };
    assert_eq!(eval(&label, 1.23456), Value::Str("1.23 kWh".into()));
    let mixed = Expr::Concat { parts: vec![konst(Value::Str("n=".into())), konst(Value::Int(3)), c(0.5)] };
    assert_eq!(eval(&mixed, 0.0), Value::Str("n=30.5".into()));
}

#[test]
fn clamp_min_max_atan2() {
    let e = Expr::Clamp { a: b(Expr::Time), lo: b(c(0.0)), hi: b(c(1.0)) };
    assert_eq!(eval(&e, -2.0), float(0.0));
    assert_eq!(eval(&e, 0.3), float(0.3));
    assert_eq!(eval(&e, 5.0), float(1.0));
    assert_eq!(eval(&bin(BinOp::Max, c(0.0), c(-3.0)), 0.0), float(0.0));
    assert_eq!(eval(&bin(BinOp::Min, c(0.0), c(-3.0)), 0.0), float(-3.0));
    assert_eq!(eval(&bin(BinOp::Atan2, c(0.0), c(1.0)), 0.0), float(0.0));
}

#[test]
fn mix_numbers_vectors_colors() {
    let m = Expr::Mix { a: b(c(0.0)), b: b(c(10.0)), t: b(Expr::Time) };
    assert_eq!(eval(&m, 0.25), float(2.5));
    let mv = Expr::Mix {
        a: b(konst(Value::Vec2([0.0, 0.0]))),
        b: b(konst(Value::Vec2([2.0, 4.0]))),
        t: b(c(0.5)),
    };
    assert_eq!(eval(&mv, 0.0), Value::Vec2([1.0, 2.0]));
    let (ca, cb) = ([1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 1.0]);
    let mc = Expr::Mix { a: b(konst(Value::Color(ca))), b: b(konst(Value::Color(cb))), t: b(c(0.5)) };
    assert_eq!(eval(&mc, 0.0), Value::Color(color::mix(ca, cb, 0.5)));
}

#[test]
fn interp_is_piecewise_linear_and_clamped() {
    let e = Expr::Interp { x: b(Expr::Time), xs: vec![0.0, 6.0, 12.0], ys: vec![0.0, 6.0, 0.0] };
    assert_eq!(eval(&e, -1.0), float(0.0));
    assert_eq!(eval(&e, 3.0), float(3.0));
    assert_eq!(eval(&e, 9.0), float(3.0));
    assert_eq!(eval(&e, 20.0), float(0.0));
}

#[test]
fn table_is_sampled_at_query_time() {
    let mut s = scene(vec![]);
    s.tables.push(Table { t0: 0.0, dt: 0.5, values: vec![0.0, 1.0, 3.0] });
    let ev = Evaluator::new(&s);
    let e = Expr::Table { table: 0 };
    assert_eq!(ev.expr(&e, 0.25, &R), float(0.5));
    assert_eq!(ev.expr(&e, 0.75, &R), float(2.0));
    assert_eq!(ev.expr(&e, 9.0, &R), float(3.0));
    assert_eq!(ev.expr(&Expr::Table { table: 5 }, 0.0, &R), Value::None);
}

#[test]
fn noise_is_deterministic_and_bounded() {
    let e = Expr::Noise { a: b(Expr::Time), seed: 42 };
    for i in 0..200 {
        let t = i as f64 * 0.05;
        let v = eval(&e, t).as_f64();
        assert!((-1.0..=1.0).contains(&v));
        assert_eq!(v, noise::noise1(t, 42));
    }
}

#[test]
fn sig_reads_signal_value() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 1.0, val(float(4.0)))])]);
    let ev = Evaluator::new(&s);
    assert_eq!(ev.expr(&sig(0), 0.5, &R), float(2.0));
}

#[test]
fn age_and_derived_default_to_resolver() {
    assert_eq!(eval(&Expr::Age { obj: 0 }, 3.0), float(0.0));
    assert_eq!(eval(&Expr::Derived { obj: 0, prop: "width".into(), world: false }, 3.0), Value::None);
}
