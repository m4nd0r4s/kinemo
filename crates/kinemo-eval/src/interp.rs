//! Value interpolation according to a signal's [`Lerp`] mode.
//!
//! | Values                   | `Linear` / `Pointwise`                 |
//! | ------------------------ | -------------------------------------- |
//! | `F` / mixed `F`,`I`      | linear                                 |
//! | `I`, `I`                 | linear, rounded                        |
//! | `V2`                     | componentwise linear                   |
//! | `C`                      | OKLab (see [`crate::color::mix`])      |
//! | `L` of `V2` (Pointwise)  | resampled to equal length, pointwise   |
//! | `B`, `S`, `Obj`, `L`, …  | step at the end (`t >= 1`)             |
//!
//! `StepEnd` / `StepStart` step at the end / start for every type, `Round`
//! rounds numeric results, and `Layout` returns `b` only once `t >= 1`
//! (the layout crate performs the real blend).

use crate::color;
use kinemo_ir::{Lerp, Value};

/// Interpolates from `a` (at `t = 0`) to `b` (at `t = 1`). `t` may exceed
/// `[0, 1]` (overshooting easings); numeric results extrapolate.
pub fn lerp_value(a: &Value, b: &Value, t: f64, lerp: Lerp) -> Value {
    match lerp {
        Lerp::Layout | Lerp::StepEnd => step(a, b, t >= 1.0),
        Lerp::StepStart => step(a, b, t > 0.0),
        Lerp::Round => match numeric(a, b, t) {
            Some(Value::Float(x)) => Value::Float(x.round()),
            Some(Value::Vec2([x, y])) => Value::Vec2([x.round(), y.round()]),
            Some(v) => v,
            None => step(a, b, t >= 1.0),
        },
        Lerp::Linear => numeric(a, b, t).unwrap_or_else(|| step(a, b, t >= 1.0)),
        Lerp::Pointwise => match (a, b) {
            (Value::List(la), Value::List(lb)) => pointwise(la, lb, t).unwrap_or_else(|| step(a, b, t >= 1.0)),
            _ => numeric(a, b, t).unwrap_or_else(|| step(a, b, t >= 1.0)),
        },
    }
}

/// Whether `lerp_value(a, b, ..)` blends continuously (as opposed to stepping).
pub fn is_continuous(a: &Value, b: &Value, lerp: Lerp) -> bool {
    match lerp {
        Lerp::Layout | Lerp::StepEnd | Lerp::StepStart => false,
        Lerp::Round | Lerp::Linear => numeric(a, b, 0.5).is_some(),
        Lerp::Pointwise => match (a, b) {
            (Value::List(la), Value::List(lb)) => pointwise(la, lb, 0.5).is_some(),
            _ => numeric(a, b, 0.5).is_some(),
        },
    }
}

/// Unclamped mix used by `Expr::Mix`: numbers, vectors and colors blend,
/// anything else steps at `t >= 1`.
pub fn mix_value(a: &Value, b: &Value, t: f64) -> Value {
    numeric(a, b, t).unwrap_or_else(|| step(a, b, t >= 1.0))
}

fn step(a: &Value, b: &Value, take_b: bool) -> Value {
    if take_b { b.clone() } else { a.clone() }
}

#[inline]
pub(crate) fn lerp_f(a: f64, b: f64, t: f64) -> f64 {
    // Exact at both endpoints.
    a * (1.0 - t) + b * t
}

fn numeric(a: &Value, b: &Value, t: f64) -> Option<Value> {
    Some(match (a, b) {
        (Value::Int(x), Value::Int(y)) => Value::Int(lerp_f(*x as f64, *y as f64, t).round() as i64),
        (Value::Float(_) | Value::Int(_), Value::Float(_) | Value::Int(_)) => Value::Float(lerp_f(a.as_f64(), b.as_f64(), t)),
        (Value::Vec2(x), Value::Vec2(y)) => Value::Vec2(lerp_v2(*x, *y, t)),
        (Value::Color(x), Value::Color(y)) => Value::Color(color::mix(*x, *y, t)),
        _ => return None,
    })
}

fn lerp_v2(a: [f64; 2], b: [f64; 2], t: f64) -> [f64; 2] {
    [lerp_f(a[0], b[0], t), lerp_f(a[1], b[1], t)]
}

/// Pointwise blend of two lists. Lists of `V2` of different lengths are
/// matched by arc length: the shorter polyline is sampled at the longer
/// one's normalized arc-length positions. Other lists must have equal
/// lengths and interpolable elements.
fn pointwise(a: &[Value], b: &[Value], t: f64) -> Option<Value> {
    if t == 1.0 {
        return Some(Value::List(b.to_vec()));
    }
    if a.is_empty() || b.is_empty() {
        return None;
    }
    if let (Some(pa), Some(pb)) = (points(a), points(b)) {
        let (pa, pb) = if pa.len() >= pb.len() {
            let fr = fractions(&pa);
            (pa, resample(&pb, &fr))
        } else {
            let fr = fractions(&pb);
            (resample(&pa, &fr), pb)
        };
        return Some(Value::List(pa.iter().zip(&pb).map(|(x, y)| Value::Vec2(lerp_v2(*x, *y, t))).collect()));
    }
    if a.len() != b.len() {
        return None;
    }
    a.iter().zip(b).map(|(x, y)| numeric(x, y, t)).collect::<Option<Vec<_>>>().map(Value::List)
}

fn points(l: &[Value]) -> Option<Vec<[f64; 2]>> {
    l.iter().map(|v| if let Value::Vec2(p) = v { Some(*p) } else { None }).collect()
}

/// Normalized cumulative arc length at each vertex (index-based if degenerate).
fn fractions(p: &[[f64; 2]]) -> Vec<f64> {
    let mut acc = Vec::with_capacity(p.len());
    let mut total = 0.0;
    acc.push(0.0);
    for w in p.windows(2) {
        total += (w[1][0] - w[0][0]).hypot(w[1][1] - w[0][1]);
        acc.push(total);
    }
    if total > 0.0 {
        acc.iter().map(|d| d / total).collect()
    } else {
        let n = (p.len().max(2) - 1) as f64;
        (0..p.len()).map(|i| i as f64 / n).collect()
    }
}

/// Samples polyline `p` at normalized arc-length positions `at`.
fn resample(p: &[[f64; 2]], at: &[f64]) -> Vec<[f64; 2]> {
    if p.len() == 1 {
        return vec![p[0]; at.len()];
    }
    let fr = fractions(p);
    let mut seg = 0;
    at.iter()
        .map(|&s| {
            while seg + 2 < fr.len() && fr[seg + 1] < s {
                seg += 1;
            }
            let span = fr[seg + 1] - fr[seg];
            let u = if span > 0.0 { ((s - fr[seg]) / span).clamp(0.0, 1.0) } else { 0.0 };
            lerp_v2(p[seg], p[seg + 1], u)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pts(v: &[[f64; 2]]) -> Value {
        Value::List(v.iter().map(|p| Value::Vec2(*p)).collect())
    }

    #[test]
    fn numbers() {
        assert_eq!(lerp_value(&Value::Float(1.0), &Value::Float(3.0), 0.5, Lerp::Linear), Value::Float(2.0));
        assert_eq!(lerp_value(&Value::Int(0), &Value::Float(1.0), 0.25, Lerp::Linear), Value::Float(0.25));
        assert_eq!(lerp_value(&Value::Int(0), &Value::Int(10), 0.26, Lerp::Linear), Value::Int(3));
        assert_eq!(lerp_value(&Value::Float(0.0), &Value::Float(10.0), 0.26, Lerp::Round), Value::Float(3.0));
        assert_eq!(lerp_value(&Value::Float(0.0), &Value::Float(10.0), 1.5, Lerp::Linear), Value::Float(15.0));
        let (a, b) = (Value::Float(0.1), Value::Float(0.7));
        assert_eq!(lerp_value(&a, &b, 1.0, Lerp::Linear), b);
        assert_eq!(lerp_value(&a, &b, 0.0, Lerp::Linear), a);
    }

    #[test]
    fn vectors_and_colors() {
        let v = lerp_value(&Value::Vec2([0.0, 2.0]), &Value::Vec2([4.0, 0.0]), 0.25, Lerp::Linear);
        assert_eq!(v, Value::Vec2([1.0, 1.5]));
        let a = Value::Color([1.0, 0.0, 0.0, 1.0]);
        let b = Value::Color([0.0, 0.0, 1.0, 1.0]);
        assert_eq!(lerp_value(&a, &b, 0.5, Lerp::Linear), Value::Color(color::mix(a.as_color(), b.as_color(), 0.5)));
    }

    #[test]
    fn discrete_types_step_at_end() {
        let a = Value::Str("a".into());
        let b = Value::Str("b".into());
        assert_eq!(lerp_value(&a, &b, 0.99, Lerp::Linear), a);
        assert_eq!(lerp_value(&a, &b, 1.0, Lerp::Linear), b);
        assert_eq!(lerp_value(&Value::Bool(false), &Value::Bool(true), 0.5, Lerp::Linear), Value::Bool(false));
        assert_eq!(lerp_value(&Value::Object(1), &Value::Object(2), 1.0, Lerp::Linear), Value::Object(2));
        let la = Value::List(vec![Value::Float(0.0)]);
        let lb = Value::List(vec![Value::Float(1.0)]);
        assert_eq!(lerp_value(&la, &lb, 0.5, Lerp::Linear), la);
        assert!(!is_continuous(&la, &lb, Lerp::Linear));
        assert!(is_continuous(&la, &lb, Lerp::Pointwise));
    }

    #[test]
    fn step_modes() {
        let (a, b) = (Value::Float(0.0), Value::Float(1.0));
        assert_eq!(lerp_value(&a, &b, 0.0, Lerp::StepStart), a);
        assert_eq!(lerp_value(&a, &b, 0.01, Lerp::StepStart), b);
        assert_eq!(lerp_value(&a, &b, 0.99, Lerp::StepEnd), a);
        assert_eq!(lerp_value(&a, &b, 1.0, Lerp::StepEnd), b);
        assert_eq!(lerp_value(&a, &b, 0.5, Lerp::Layout), a);
        assert_eq!(lerp_value(&a, &b, 1.0, Lerp::Layout), b);
    }

    #[test]
    fn pointwise_equal_lengths() {
        let a = pts(&[[0.0, 0.0], [2.0, 0.0]]);
        let b = pts(&[[0.0, 2.0], [2.0, 2.0]]);
        assert_eq!(lerp_value(&a, &b, 0.5, Lerp::Pointwise), pts(&[[0.0, 1.0], [2.0, 1.0]]));
    }

    #[test]
    fn pointwise_resamples_shorter() {
        let a = pts(&[[0.0, 0.0], [4.0, 0.0]]);
        let b = pts(&[[0.0, 1.0], [1.0, 1.0], [4.0, 1.0]]);
        // `a` sampled at b's arc fractions (0, 0.25, 1) → (0,0), (1,0), (4,0).
        let m = lerp_value(&a, &b, 0.5, Lerp::Pointwise);
        assert_eq!(m, pts(&[[0.0, 0.5], [1.0, 0.5], [4.0, 0.5]]));
        // Endpoints are exact.
        assert_eq!(lerp_value(&a, &b, 0.0, Lerp::Pointwise), pts(&[[0.0, 0.0], [1.0, 0.0], [4.0, 0.0]]));
        assert_eq!(lerp_value(&a, &b, 1.0, Lerp::Pointwise), b);
        // Reverse direction.
        let m2 = lerp_value(&b, &a, 0.5, Lerp::Pointwise);
        assert_eq!(m2, pts(&[[0.0, 0.5], [1.0, 0.5], [4.0, 0.5]]));
    }

    #[test]
    fn pointwise_single_and_degenerate() {
        let a = pts(&[[1.0, 1.0]]);
        let b = pts(&[[0.0, 0.0], [2.0, 0.0]]);
        assert_eq!(lerp_value(&a, &b, 0.5, Lerp::Pointwise), pts(&[[0.5, 0.5], [1.5, 0.5]]));
        let empty = Value::List(vec![]);
        assert_eq!(lerp_value(&empty, &b, 0.5, Lerp::Pointwise), empty);
        let same = pts(&[[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]);
        assert_eq!(lerp_value(&same, &b, 0.0, Lerp::Pointwise), same);
        assert_eq!(lerp_value(&same, &b, 0.5, Lerp::Pointwise), pts(&[[0.5, 0.5], [1.0, 0.5], [1.5, 0.5]]));
    }

    #[test]
    fn mix_value_extrapolates() {
        assert_eq!(mix_value(&Value::Float(0.0), &Value::Float(2.0), 2.0), Value::Float(4.0));
        assert_eq!(mix_value(&Value::Str("x".into()), &Value::Float(2.0), 0.5), Value::Str("x".into()));
    }
}
