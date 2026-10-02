//! Shared scene-building helpers for the integration tests.
#![allow(dead_code)]

use kinemo_ir::{BinOp, Blend, Ease, Entry, Expr, Lerp, Scene, SceneConfig, Signal, Span, Src, Value};

pub fn float(x: f64) -> Value {
    Value::Float(x)
}

pub fn val(v: Value) -> Src {
    Src::Val { v }
}

pub fn ex(e: Expr) -> Src {
    Src::Expr { e }
}

pub fn konst(v: Value) -> Expr {
    Expr::Const { v }
}

pub fn sig(id: u32) -> Expr {
    Expr::Sig { id }
}

pub fn bin(f: BinOp, a: Expr, b: Expr) -> Expr {
    Expr::Bin { f, a: Box::new(a), b: Box::new(b) }
}

pub fn set(t: f64, src: Src) -> Entry {
    Entry::Set { t, src, span: Span::default() }
}

/// Linear-eased replace animation.
pub fn anim(t0: f64, t1: f64, to: Src) -> Entry {
    anim_with(t0, t1, to, None, Ease::Linear, Blend::Replace)
}

/// Linear-eased additive animation.
pub fn add(t0: f64, t1: f64, delta: Src) -> Entry {
    anim_with(t0, t1, delta, None, Ease::Linear, Blend::Add)
}

pub fn anim_with(t0: f64, t1: f64, to: Src, from: Option<Src>, ease: Ease, blend: Blend) -> Entry {
    Entry::Anim { t0, t1, to, from, ease, blend, span: Span::default() }
}

/// Builds a signal whose id is its position in the list passed to [`scene`].
pub fn signal(initial: Value, lerp: Lerp, timeline: Vec<Entry>) -> Signal {
    Signal { id: 0, initial, lerp, timeline, owner: None, span: Span::default() }
}

pub fn num(initial: f64, timeline: Vec<Entry>) -> Signal {
    signal(float(initial), Lerp::Linear, timeline)
}

pub fn scene(signals: Vec<Signal>) -> Scene {
    let mut s = Scene::new(SceneConfig::default());
    s.signals = signals
        .into_iter()
        .enumerate()
        .map(|(i, mut sg)| {
            sg.id = i as u32;
            sg
        })
        .collect();
    s
}

pub fn assert_close(v: &Value, expected: f64) {
    match v {
        Value::Float(x) => assert!((x - expected).abs() < 1e-9, "expected {expected}, got {x}"),
        other => panic!("expected Float({expected}), got {other:?}"),
    }
}

pub fn assert_close_v2(v: &Value, expected: [f64; 2]) {
    match v {
        Value::Vec2([x, y]) => {
            assert!((x - expected[0]).abs() < 1e-9 && (y - expected[1]).abs() < 1e-9, "expected {expected:?}, got {v:?}")
        }
        other => panic!("expected Vec2({expected:?}), got {other:?}"),
    }
}
