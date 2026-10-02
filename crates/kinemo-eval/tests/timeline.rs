//! Timeline semantics contract: sets, replace/additive animations, bindings.

mod common;

use common::*;
use kinemo_eval::{ease, Evaluated, Evaluator, NoResolver};
use kinemo_ir::{BinOp, Blend, Ease, Expr, Lerp, Value};

const R: NoResolver = NoResolver;

fn at(scene: &kinemo_ir::Scene, id: u32, t: f64) -> Value {
    Evaluator::new(scene).signal(id, t, &R)
}

#[test]
fn initial_value_without_entries() {
    let s = scene(vec![num(2.0, vec![])]);
    assert_close(&at(&s, 0, -5.0), 2.0);
    assert_close(&at(&s, 0, 100.0), 2.0);
}

#[test]
fn unknown_signal_is_none() {
    let s = scene(vec![]);
    let ev = Evaluator::new(&s);
    assert_eq!(ev.signal(3, 0.0, &R), Value::None);
    assert_eq!(ev.signal_raw(3, 0.0, &R), Evaluated::Value(Value::None));
}

#[test]
fn set_applies_from_its_time() {
    let s = scene(vec![num(0.0, vec![set(1.0, val(float(5.0)))])]);
    assert_close(&at(&s, 0, 0.999), 0.0);
    assert_close(&at(&s, 0, 1.0), 5.0);
    assert_close(&at(&s, 0, 9.0), 5.0);
}

#[test]
fn set_expr_is_a_live_binding() {
    // s1 animates 0→10 over [0, 1]; s0 is bound to 2·s1 from t = 0.
    let s = scene(vec![
        num(0.0, vec![set(0.0, ex(bin(BinOp::Mul, sig(1), konst(float(2.0)))))]),
        num(0.0, vec![anim(0.0, 1.0, val(float(10.0)))]),
    ]);
    let ev = Evaluator::new(&s);
    assert_close(&ev.signal(0, 0.25, &R), 5.0);
    assert_close(&ev.signal(0, 0.5, &R), 10.0);
    assert_close(&ev.signal(0, 3.0, &R), 20.0);
}

#[test]
fn replace_anim_phases() {
    let s = scene(vec![num(1.0, vec![anim(1.0, 3.0, val(float(5.0)))])]);
    assert_close(&at(&s, 0, 0.5), 1.0);
    assert_close(&at(&s, 0, 1.0), 1.0);
    assert_close(&at(&s, 0, 2.0), 3.0);
    assert_close(&at(&s, 0, 3.0), 5.0);
    assert_close(&at(&s, 0, 10.0), 5.0);
}

#[test]
fn anim_uses_its_easing() {
    let e = Ease::Smooth;
    let s = scene(vec![num(0.0, vec![anim_with(0.0, 1.0, val(float(10.0)), None, e.clone(), Blend::Replace)])]);
    assert_close(&at(&s, 0, 0.25), 10.0 * ease::apply(&e, 0.25));
    let ev = Evaluator::new(&s);
    match ev.signal_raw(0, 0.25, &R) {
        Evaluated::Transition { from, to, alpha } => {
            assert_close(&from, 0.0);
            assert_close(&to, 10.0);
            assert!((alpha - ease::apply(&e, 0.25)).abs() < 1e-12, "alpha is eased");
        }
        other => panic!("expected transition, got {other:?}"),
    }
    assert_eq!(ev.signal_raw(0, 1.0, &R), Evaluated::Value(float(10.0)));
}

#[test]
fn overshooting_ease_extrapolates() {
    let s = scene(vec![num(0.0, vec![anim_with(0.0, 1.0, val(float(1.0)), None, Ease::OutBack, Blend::Replace)])]);
    let peak = (1..100).map(|i| at(&s, 0, i as f64 / 100.0).as_f64()).fold(f64::MIN, f64::max);
    assert!(peak > 1.05);
}

#[test]
fn from_is_a_snapshot_at_t0_not_live() {
    // Base bound to time; anim over [2, 4] to 10 starts from time(2) = 2.
    let s = scene(vec![num(0.0, vec![set(0.0, ex(Expr::Time)), anim(2.0, 4.0, val(float(10.0)))])]);
    assert_close(&at(&s, 0, 1.0), 1.0);
    assert_close(&at(&s, 0, 2.0), 2.0);
    assert_close(&at(&s, 0, 3.0), 6.0); // live from would give 6.5
}

#[test]
fn explicit_from_is_evaluated_at_t0() {
    let s = scene(vec![num(
        0.0,
        vec![anim_with(2.0, 4.0, val(float(10.0)), Some(ex(Expr::Time)), Ease::Linear, Blend::Replace)],
    )]);
    assert_close(&at(&s, 0, 1.0), 0.0);
    assert_close(&at(&s, 0, 2.0), 2.0);
    assert_close(&at(&s, 0, 3.0), 6.0);
}

#[test]
fn expr_target_is_live_and_becomes_binding() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 2.0, ex(Expr::Time))])]);
    assert_close(&at(&s, 0, 1.0), 0.5); // lerp(0, time=1, 0.5)
    assert_close(&at(&s, 0, 2.0), 2.0);
    assert_close(&at(&s, 0, 7.0), 7.0); // keeps tracking
}

#[test]
fn zero_duration_anim_acts_like_set() {
    let s = scene(vec![num(0.0, vec![anim(1.0, 1.0, val(float(4.0))), anim(2.0, 1.5, val(float(8.0)))])]);
    assert_close(&at(&s, 0, 0.9), 0.0);
    assert_close(&at(&s, 0, 1.0), 4.0);
    assert_close(&at(&s, 0, 1.9), 4.0);
    assert_close(&at(&s, 0, 2.0), 8.0);
}

#[test]
fn sequential_anims_chain() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 1.0, val(float(5.0))), anim(1.0, 2.0, val(float(0.0)))])]);
    assert_close(&at(&s, 0, 0.5), 2.5);
    assert_close(&at(&s, 0, 1.0), 5.0);
    assert_close(&at(&s, 0, 1.5), 2.5);
    assert_close(&at(&s, 0, 2.0), 0.0);
}

#[test]
fn later_start_overrides_running_anim() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 4.0, val(float(10.0))), set(2.0, val(float(100.0)))])]);
    assert_close(&at(&s, 0, 1.0), 2.5);
    assert_close(&at(&s, 0, 3.0), 100.0);
    assert_close(&at(&s, 0, 5.0), 100.0);
}

#[test]
fn entries_are_sorted_stably_by_start() {
    // Out of order in the list; two sets at t = 1 → the later one in the list wins.
    let s = scene(vec![num(
        0.0,
        vec![set(3.0, val(float(30.0))), set(1.0, val(float(10.0))), set(1.0, val(float(11.0)))],
    )]);
    assert_close(&at(&s, 0, 0.5), 0.0);
    assert_close(&at(&s, 0, 2.0), 11.0);
    assert_close(&at(&s, 0, 3.0), 30.0);
}

#[test]
fn overlapping_replace_later_in_list_wins() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 2.0, val(float(10.0))), anim(1.0, 3.0, val(float(-10.0)))])]);
    // Second anim starts from the first one's value at t = 1 (5).
    assert_close(&at(&s, 0, 1.0), 5.0);
    assert_close(&at(&s, 0, 1.5), 5.0 + (-15.0) * 0.25);
    assert_close(&at(&s, 0, 3.0), -10.0);
}

#[test]
fn additive_anim_offsets_base() {
    let s = scene(vec![num(1.0, vec![add(0.0, 2.0, val(float(4.0)))])]);
    assert_close(&at(&s, 0, -1.0), 1.0);
    assert_close(&at(&s, 0, 1.0), 3.0);
    assert_close(&at(&s, 0, 2.0), 5.0);
    assert_close(&at(&s, 0, 9.0), 5.0);
}

#[test]
fn additive_on_top_of_replace() {
    let s = scene(vec![num(0.0, vec![anim(0.0, 2.0, val(float(10.0))), add(0.0, 2.0, val(float(2.0)))])]);
    assert_close(&at(&s, 0, 1.0), 6.0);
    assert_close(&at(&s, 0, 2.0), 12.0);
    let ev = Evaluator::new(&s);
    match ev.signal_raw(0, 1.0, &R) {
        Evaluated::Transition { from, to, .. } => {
            assert_close(&from, 1.0);
            assert_close(&to, 11.0);
        }
        other => panic!("expected transition, got {other:?}"),
    }
}

#[test]
fn finished_additive_is_absorbed_by_later_set() {
    let s = scene(vec![num(0.0, vec![add(0.0, 1.0, val(float(2.0))), set(2.0, val(float(0.0)))])]);
    assert_close(&at(&s, 0, 1.5), 2.0);
    assert_close(&at(&s, 0, 3.0), 0.0);
}

#[test]
fn running_additive_survives_later_set() {
    let s = scene(vec![num(0.0, vec![add(0.0, 4.0, val(float(4.0))), set(2.0, val(float(10.0)))])]);
    assert_close(&at(&s, 0, 3.0), 13.0);
    assert_close(&at(&s, 0, 5.0), 14.0);
}

#[test]
fn replace_during_running_additive_is_continuous() {
    let s = scene(vec![num(0.0, vec![add(0.0, 4.0, val(float(4.0))), anim(2.0, 3.0, val(float(10.0)))])]);
    let before = at(&s, 0, 2.0 - 1e-9).as_f64();
    let start = at(&s, 0, 2.0).as_f64();
    assert!((before - start).abs() < 1e-6, "{before} vs {start}");
    assert_close(&at(&s, 0, 2.0), 2.0);
    assert_close(&at(&s, 0, 3.0), 13.0);
    assert_close(&at(&s, 0, 4.0), 14.0);
}

#[test]
fn replace_after_finished_additive_starts_from_sum() {
    let s = scene(vec![num(0.0, vec![add(0.0, 1.0, val(float(2.0))), anim(2.0, 4.0, val(float(10.0)))])]);
    assert_close(&at(&s, 0, 2.0), 2.0);
    assert_close(&at(&s, 0, 3.0), 6.0);
    assert_close(&at(&s, 0, 5.0), 10.0);
}

#[test]
fn additive_vectors() {
    let s = scene(vec![signal(
        Value::Vec2([1.0, 1.0]),
        Lerp::Linear,
        vec![add(0.0, 1.0, val(Value::Vec2([2.0, -2.0])))],
    )]);
    assert_close_v2(&at(&s, 0, 0.5), [2.0, 0.0]);
    assert_close_v2(&at(&s, 0, 1.0), [3.0, -1.0]);
}

#[test]
fn additive_ignored_for_non_numeric() {
    let s = scene(vec![signal(Value::Str("a".into()), Lerp::Linear, vec![add(0.0, 1.0, val(float(1.0)))])]);
    assert_eq!(at(&s, 0, 2.0), Value::Str("a".into()));
}

#[test]
fn discrete_values_step_at_end() {
    let s = scene(vec![signal(Value::Str("a".into()), Lerp::Linear, vec![anim(0.0, 1.0, val(Value::Str("b".into())))])]);
    assert_eq!(at(&s, 0, 0.0), Value::Str("a".into()));
    assert_eq!(at(&s, 0, 0.99), Value::Str("a".into()));
    assert_eq!(at(&s, 0, 1.0), Value::Str("b".into()));
}

#[test]
fn discrete_values_do_not_step_early_on_overshoot() {
    let s = scene(vec![signal(
        Value::Bool(false),
        Lerp::Linear,
        vec![anim_with(0.0, 1.0, val(Value::Bool(true)), None, Ease::OutBack, Blend::Replace)],
    )]);
    assert_eq!(at(&s, 0, 0.7), Value::Bool(false));
    assert_eq!(at(&s, 0, 1.0), Value::Bool(true));
}

#[test]
fn step_start_mode() {
    let s = scene(vec![signal(float(0.0), Lerp::StepStart, vec![anim(1.0, 2.0, val(float(5.0)))])]);
    assert_close(&at(&s, 0, 0.9), 0.0);
    assert_close(&at(&s, 0, 1.0), 5.0);
    assert_close(&at(&s, 0, 1.5), 5.0);
}

#[test]
fn step_end_mode() {
    let s = scene(vec![signal(float(0.0), Lerp::StepEnd, vec![anim(1.0, 2.0, val(float(5.0)))])]);
    assert_close(&at(&s, 0, 1.9), 0.0);
    assert_close(&at(&s, 0, 2.0), 5.0);
}

#[test]
fn integers_round() {
    let s = scene(vec![signal(Value::Int(0), Lerp::Round, vec![anim(0.0, 1.0, val(Value::Int(10)))])]);
    assert_eq!(at(&s, 0, 0.26), Value::Int(3));
    assert_eq!(at(&s, 0, 1.0), Value::Int(10));
}

#[test]
fn colors_mix_in_oklab() {
    let (a, b) = ([1.0, 0.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0]);
    let s = scene(vec![signal(Value::Color(a), Lerp::Linear, vec![anim(0.0, 1.0, val(Value::Color(b)))])]);
    assert_eq!(at(&s, 0, 0.5), Value::Color(kinemo_eval::color::mix(a, b, 0.5)));
}

#[test]
fn layout_signals_expose_transition() {
    let l0 = Value::List(vec![Value::Object(1)]);
    let l1 = Value::List(vec![Value::Object(1), Value::Object(2)]);
    let s = scene(vec![signal(l0.clone(), Lerp::Layout, vec![anim(0.0, 1.0, val(l1.clone()))])]);
    let ev = Evaluator::new(&s);
    assert_eq!(ev.signal(0, 0.5, &R), l0);
    assert_eq!(ev.signal(0, 1.0, &R), l1);
    match ev.signal_raw(0, 0.5, &R) {
        Evaluated::Transition { from, to, alpha } => {
            assert_eq!((from, to), (l0, l1));
            assert!((alpha - ease::apply(&Ease::Linear, 0.5)).abs() < 1e-12);
        }
        other => panic!("expected transition, got {other:?}"),
    }
}

#[test]
fn pointwise_signal() {
    let p0 = Value::List(vec![Value::Vec2([0.0, 0.0]), Value::Vec2([2.0, 0.0])]);
    let p1 = Value::List(vec![Value::Vec2([0.0, 2.0]), Value::Vec2([2.0, 2.0])]);
    let s = scene(vec![signal(p0, Lerp::Pointwise, vec![anim(0.0, 1.0, val(p1))])]);
    assert_eq!(at(&s, 0, 0.5), Value::List(vec![Value::Vec2([0.0, 1.0]), Value::Vec2([2.0, 1.0])]));
}
