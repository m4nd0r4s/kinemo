//! Reactive plumbing: resolver callbacks, re-entrancy, cycles and memoization.

mod common;

use common::*;
use kinemo_eval::{Evaluator, NoResolver, Resolver};
use kinemo_ir::{BinOp, Expr, ObjectId, Value};
use std::cell::Cell;

/// A fake layout: `width` of object `obj` is `2 · signal(obj)`; ages start at t = 1.
struct FakeLayout {
    calls: Cell<usize>,
}

impl Resolver for FakeLayout {
    fn derived(&self, ev: &Evaluator, obj: ObjectId, prop: &str, world: bool, t: f64) -> Value {
        self.calls.set(self.calls.get() + 1);
        let v = ev.signal(obj, t, self).as_f64();
        match (prop, world) {
            ("width", false) => float(2.0 * v),
            ("width", true) => float(2.0 * v + 100.0),
            _ => Value::None,
        }
    }
    fn age(&self, _: &Evaluator, _: ObjectId, t: f64) -> f64 {
        (t - 1.0).max(0.0)
    }
}

#[test]
fn resolver_can_reenter_evaluator() {
    // s0 animates 0→5; s1 is bound to derived width of object 0 (= 2·s0).
    let width = Expr::Derived { obj: 0, prop: "width".into(), world: false };
    let s = scene(vec![num(0.0, vec![anim(0.0, 1.0, val(float(5.0)))]), num(0.0, vec![set(0.0, ex(width))])]);
    let r = FakeLayout { calls: Cell::new(0) };
    let ev = Evaluator::new(&s);
    assert_close(&ev.signal(1, 0.5, &r), 5.0);
    assert_close(&ev.signal(1, 2.0, &r), 10.0);
    let world = Expr::Derived { obj: 0, prop: "width".into(), world: true };
    assert_close(&ev.expr(&world, 2.0, &r), 110.0);
}

#[test]
fn age_comes_from_resolver() {
    let r = FakeLayout { calls: Cell::new(0) };
    let s = scene(vec![]);
    let ev = Evaluator::new(&s);
    assert_close(&ev.expr(&Expr::Age { obj: 3 }, 3.5, &r), 2.5);
}

#[test]
fn memoizes_per_signal_and_time() {
    let width = Expr::Derived { obj: 0, prop: "width".into(), world: false };
    let s = scene(vec![num(1.0, vec![]), num(0.0, vec![set(0.0, ex(width))])]);
    let r = FakeLayout { calls: Cell::new(0) };
    let ev = Evaluator::new(&s);
    ev.signal(1, 0.5, &r);
    ev.signal(1, 0.5, &r);
    assert_eq!(r.calls.get(), 1);
    ev.signal(1, 0.75, &r);
    assert_eq!(r.calls.get(), 2);
    assert!(ev.cached_values() >= 2);
    ev.clear();
    assert_eq!(ev.cached_values(), 0);
    ev.signal(1, 0.5, &r);
    assert_eq!(r.calls.get(), 3);
}

#[test]
fn self_cycle_returns_none() {
    let s = scene(vec![num(0.0, vec![set(0.0, ex(sig(0)))])]);
    let ev = Evaluator::new(&s);
    assert_eq!(ev.signal(0, 1.0, &NoResolver), Value::None);
    // Before the binding the initial value is still visible.
    assert_close(&ev.signal(0, -1.0, &NoResolver), 0.0);
}

#[test]
fn mutual_cycle_terminates() {
    let s = scene(vec![
        num(0.0, vec![set(0.0, ex(bin(BinOp::Add, sig(1), konst(float(1.0)))))]),
        num(0.0, vec![set(0.0, ex(sig(0)))]),
    ]);
    let ev = Evaluator::new(&s);
    // Must not overflow the stack; the exact value of a cut cycle is unspecified.
    let _ = ev.signal(0, 1.0, &NoResolver);
    let _ = ev.signal(1, 1.0, &NoResolver);
}

#[test]
fn cycle_through_from_snapshot_terminates() {
    // Explicit `from` reading the signal itself at t0.
    let s = scene(vec![num(
        3.0,
        vec![anim_with(
            1.0,
            2.0,
            val(float(10.0)),
            Some(ex(sig(0))),
            kinemo_ir::Ease::Linear,
            kinemo_ir::Blend::Replace,
        )],
    )]);
    let ev = Evaluator::new(&s);
    let _ = ev.signal(0, 1.5, &NoResolver);
    assert_close(&ev.signal(0, 2.0, &NoResolver), 10.0);
}

#[test]
fn snapshot_of_own_history_is_not_a_cycle() {
    // An anim's start value reads the same signal at t0 through earlier entries.
    let s = scene(vec![num(
        0.0,
        vec![anim(0.0, 1.0, val(float(4.0))), anim(1.0, 2.0, ex(bin(BinOp::Mul, Expr::Time, konst(float(2.0)))))],
    )]);
    let ev = Evaluator::new(&s);
    assert_close(&ev.signal(0, 1.5, &NoResolver), 3.5); // lerp(4, 3, 0.5)
    assert_close(&ev.signal(0, 3.0, &NoResolver), 6.0);
}

#[test]
fn many_chained_signals() {
    // s_i = s_{i-1} + 1, 300 deep, evaluated at several times.
    let mut sigs = vec![num(0.0, vec![set(0.0, ex(Expr::Time))])];
    for i in 1..300u32 {
        sigs.push(num(0.0, vec![set(0.0, ex(bin(BinOp::Add, sig(i - 1), konst(float(1.0)))))]));
    }
    let s = scene(sigs);
    let ev = Evaluator::new(&s);
    for k in 0..5 {
        let t = k as f64;
        assert_close(&ev.signal(299, t, &NoResolver), t + 299.0);
    }
}
