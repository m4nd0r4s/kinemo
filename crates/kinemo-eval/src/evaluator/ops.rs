//! Pure operators on [`Value`]s used by expression evaluation and additive blending.
//!
//! Numeric rules: `I op I` stays integral for `+ - * %` (and `min`/`max`);
//! everything else is `F`. `V2` operands work componentwise with scalar
//! broadcast. Unsupported combinations produce `Value::None`.

use kinemo_ir::{BinOp, UnOp, Value};

fn is_num(v: &Value) -> bool {
    matches!(v, Value::Float(_) | Value::Int(_) | Value::Bool(_))
}

fn map_num(v: &Value, f: impl Fn(f64) -> f64) -> Value {
    match v {
        Value::Vec2([x, y]) => Value::Vec2([f(*x), f(*y)]),
        v if is_num(v) => Value::Float(f(v.as_f64())),
        _ => Value::None,
    }
}

pub(crate) fn unary(op: UnOp, a: &Value) -> Value {
    match op {
        UnOp::Neg => match a {
            Value::Int(n) => Value::Int(n.wrapping_neg()),
            _ => map_num(a, |x| -x),
        },
        UnOp::Not => Value::Bool(!a.as_bool()),
        UnOp::Abs => match a {
            Value::Int(n) => Value::Int(n.wrapping_abs()),
            _ => map_num(a, f64::abs),
        },
        UnOp::Floor | UnOp::Ceil | UnOp::Round if matches!(a, Value::Int(_)) => a.clone(),
        UnOp::Floor => map_num(a, f64::floor),
        UnOp::Ceil => map_num(a, f64::ceil),
        UnOp::Round => map_num(a, round_half_even),
        UnOp::Sin => map_num(a, f64::sin),
        UnOp::Cos => map_num(a, f64::cos),
        UnOp::Tan => map_num(a, f64::tan),
        UnOp::Exp => map_num(a, f64::exp),
        UnOp::Ln => map_num(a, f64::ln),
        UnOp::Sqrt => map_num(a, f64::sqrt),
        UnOp::X => match a {
            Value::Vec2([x, _]) => Value::Float(*x),
            v if is_num(v) => Value::Float(v.as_f64()),
            _ => Value::None,
        },
        UnOp::Y => match a {
            Value::Vec2([_, y]) => Value::Float(*y),
            v if is_num(v) => Value::Float(v.as_f64()),
            _ => Value::None,
        },
        UnOp::Len => match a {
            Value::Vec2([x, y]) => Value::Float(x.hypot(*y)),
            Value::Str(s) => Value::Int(s.chars().count() as i64),
            Value::List(l) => Value::Int(l.len() as i64),
            v if is_num(v) => Value::Float(v.as_f64().abs()),
            _ => Value::None,
        },
    }
}

/// Python's `round()`: ties to even.
fn round_half_even(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 {
        r - x.signum()
    } else {
        r
    }
}

pub(crate) fn binary(op: BinOp, a: &Value, b: &Value) -> Value {
    use BinOp::*;
    match op {
        Lt | Le | Gt | Ge => {
            if !(is_num(a) && is_num(b)) {
                return match (a, b) {
                    (Value::Str(x), Value::Str(y)) => Value::Bool(cmp_holds(op, x.cmp(y))),
                    _ => Value::None,
                };
            }
            let (x, y) = (a.as_f64(), b.as_f64());
            Value::Bool(match op {
                Lt => x < y,
                Le => x <= y,
                Gt => x > y,
                _ => x >= y,
            })
        }
        Eq => Value::Bool(equal(a, b)),
        Ne => Value::Bool(!equal(a, b)),
        And => Value::Bool(a.as_bool() && b.as_bool()),
        Or => Value::Bool(a.as_bool() || b.as_bool()),
        Add if matches!(a, Value::Str(_)) || matches!(b, Value::Str(_)) => {
            Value::Str(format!("{}{}", crate::format::display(a), crate::format::display(b)))
        }
        Add if matches!((a, b), (Value::List(_), Value::List(_))) => {
            Value::List(a.as_list().iter().chain(b.as_list()).cloned().collect())
        }
        _ => arith(op, a, b),
    }
}

fn cmp_holds(op: BinOp, o: std::cmp::Ordering) -> bool {
    use std::cmp::Ordering::*;
    match op {
        BinOp::Lt => o == Less,
        BinOp::Le => o != Greater,
        BinOp::Gt => o == Greater,
        _ => o != Less,
    }
}

fn equal(a: &Value, b: &Value) -> bool {
    if is_num(a) && is_num(b) {
        a.as_f64() == b.as_f64()
    } else {
        a == b
    }
}

fn arith(op: BinOp, a: &Value, b: &Value) -> Value {
    if let (Value::Int(x), Value::Int(y)) = (a, b) {
        if let Some(v) = int_arith(op, *x, *y) {
            return Value::Int(v);
        }
    }
    match (a, b) {
        (Value::Vec2(_), _) | (_, Value::Vec2(_)) => {
            if !(matches!(a, Value::Vec2(_)) || is_num(a)) || !(matches!(b, Value::Vec2(_)) || is_num(b)) {
                return Value::None;
            }
            let (x, y) = (a.as_v2(), b.as_v2());
            Value::Vec2([float_arith(op, x[0], y[0]), float_arith(op, x[1], y[1])])
        }
        _ if is_num(a) && is_num(b) => Value::Float(float_arith(op, a.as_f64(), b.as_f64())),
        _ => Value::None,
    }
}

fn int_arith(op: BinOp, x: i64, y: i64) -> Option<i64> {
    match op {
        BinOp::Add => x.checked_add(y),
        BinOp::Sub => x.checked_sub(y),
        BinOp::Mul => x.checked_mul(y),
        BinOp::Mod if y != 0 => Some(x.rem_euclid(y) + if y < 0 && x.rem_euclid(y) != 0 { y } else { 0 }),
        BinOp::Min => Some(x.min(y)),
        BinOp::Max => Some(x.max(y)),
        _ => None,
    }
}

fn float_arith(op: BinOp, x: f64, y: f64) -> f64 {
    match op {
        BinOp::Add => x + y,
        BinOp::Sub => x - y,
        BinOp::Mul => x * y,
        BinOp::Div => x / y,
        // Python semantics: result takes the sign of the divisor.
        BinOp::Mod => x - y * (x / y).floor(),
        BinOp::Pow => x.powf(y),
        BinOp::Min => x.min(y),
        BinOp::Max => x.max(y),
        BinOp::Atan2 => x.atan2(y),
        _ => f64::NAN,
    }
}

/// `a + b` for additive blending (numbers and vectors); other values pass `a` through.
pub(crate) fn add_offset(a: &Value, b: &Value) -> Value {
    match arith(BinOp::Add, a, b) {
        Value::None => a.clone(),
        v => v,
    }
}

/// `v * k` for numbers and vectors (integers stay integral, rounded).
pub(crate) fn scale(v: &Value, k: f64) -> Value {
    match v {
        Value::Int(n) => Value::Int((*n as f64 * k).round() as i64),
        _ => map_num(v, |x| x * k),
    }
}

/// Componentwise clamp of numbers and vectors.
pub(crate) fn clamp(a: &Value, lo: &Value, hi: &Value) -> Value {
    let lower = binary(BinOp::Max, a, lo);
    binary(BinOp::Min, &lower, hi)
}

#[cfg(test)]
mod tests {
    use super::*;
    use BinOp::*;

    #[test]
    fn integer_and_float_arithmetic() {
        assert_eq!(binary(Add, &Value::Int(2), &Value::Int(3)), Value::Int(5));
        assert_eq!(binary(Div, &Value::Int(3), &Value::Int(2)), Value::Float(1.5));
        assert_eq!(binary(Mod, &Value::Int(-7), &Value::Int(3)), Value::Int(2));
        assert_eq!(binary(Mod, &Value::Int(7), &Value::Int(-3)), Value::Int(-2));
        assert_eq!(binary(Mod, &Value::Float(-7.0), &Value::Float(3.0)), Value::Float(2.0));
        assert_eq!(binary(Pow, &Value::Int(2), &Value::Int(10)), Value::Float(1024.0));
        assert_eq!(binary(Add, &Value::Int(1), &Value::Float(0.5)), Value::Float(1.5));
        assert_eq!(binary(Atan2, &Value::Float(1.0), &Value::Float(0.0)), Value::Float(std::f64::consts::FRAC_PI_2));
        assert_eq!(binary(Add, &Value::Int(i64::MAX), &Value::Int(1)), Value::Float(i64::MAX as f64 + 1.0));
    }

    #[test]
    fn vector_broadcast() {
        let v = Value::Vec2([1.0, 2.0]);
        assert_eq!(binary(Mul, &v, &Value::Float(2.0)), Value::Vec2([2.0, 4.0]));
        assert_eq!(binary(Sub, &Value::Int(1), &v), Value::Vec2([0.0, -1.0]));
        assert_eq!(binary(Add, &v, &Value::Vec2([1.0, 1.0])), Value::Vec2([2.0, 3.0]));
        assert_eq!(binary(Div, &v, &Value::Vec2([2.0, 4.0])), Value::Vec2([0.5, 0.5]));
        assert_eq!(binary(Add, &v, &Value::Str("x".into())), Value::Str("(1.0, 2.0)x".into()));
        assert_eq!(binary(Add, &v, &Value::Object(1)), Value::None);
    }

    #[test]
    fn strings_comparisons_logic() {
        let s = |x: &str| Value::Str(x.into());
        assert_eq!(binary(Add, &s("a"), &s("b")), s("ab"));
        assert_eq!(binary(Lt, &Value::Float(1.0), &Value::Int(2)), Value::Bool(true));
        assert_eq!(binary(Ge, &Value::Float(1.0), &Value::Int(2)), Value::Bool(false));
        assert_eq!(binary(Lt, &s("a"), &s("b")), Value::Bool(true));
        assert_eq!(binary(Eq, &Value::Int(1), &Value::Float(1.0)), Value::Bool(true));
        assert_eq!(binary(Ne, &s("a"), &s("a")), Value::Bool(false));
        assert_eq!(binary(And, &Value::Bool(true), &Value::Bool(false)), Value::Bool(false));
        assert_eq!(binary(Or, &Value::Bool(true), &Value::Bool(false)), Value::Bool(true));
        assert_eq!(binary(Min, &Value::Int(3), &Value::Int(2)), Value::Int(2));
        assert_eq!(binary(Max, &Value::Float(3.0), &Value::Int(4)), Value::Float(4.0));
    }

    #[test]
    fn unary_ops() {
        assert_eq!(unary(UnOp::Neg, &Value::Vec2([1.0, -2.0])), Value::Vec2([-1.0, 2.0]));
        assert_eq!(unary(UnOp::Neg, &Value::Int(3)), Value::Int(-3));
        assert_eq!(unary(UnOp::Not, &Value::Bool(false)), Value::Bool(true));
        assert_eq!(unary(UnOp::Abs, &Value::Float(-2.5)), Value::Float(2.5));
        assert_eq!(unary(UnOp::Round, &Value::Float(2.5)), Value::Float(2.0));
        assert_eq!(unary(UnOp::Round, &Value::Float(3.5)), Value::Float(4.0));
        assert_eq!(unary(UnOp::Round, &Value::Float(-2.5)), Value::Float(-2.0));
        assert_eq!(unary(UnOp::Round, &Value::Float(2.4)), Value::Float(2.0));
        assert_eq!(unary(UnOp::Floor, &Value::Int(3)), Value::Int(3));
        assert_eq!(unary(UnOp::X, &Value::Vec2([3.0, 4.0])), Value::Float(3.0));
        assert_eq!(unary(UnOp::Y, &Value::Vec2([3.0, 4.0])), Value::Float(4.0));
        assert_eq!(unary(UnOp::Len, &Value::Vec2([3.0, 4.0])), Value::Float(5.0));
        assert_eq!(unary(UnOp::Len, &Value::Str("héllo".into())), Value::Int(5));
        assert_eq!(unary(UnOp::Sqrt, &Value::Str("x".into())), Value::None);
    }

    #[test]
    fn helpers() {
        assert_eq!(add_offset(&Value::Float(1.0), &Value::Vec2([1.0, 2.0])), Value::Vec2([2.0, 3.0]));
        assert_eq!(add_offset(&Value::Str("a".into()), &Value::Float(1.0)), Value::Str("a".into()));
        assert_eq!(scale(&Value::Vec2([1.0, 2.0]), 0.5), Value::Vec2([0.5, 1.0]));
        assert_eq!(scale(&Value::Int(3), 0.5), Value::Int(2));
        assert_eq!(clamp(&Value::Float(5.0), &Value::Float(0.0), &Value::Float(1.0)), Value::Float(1.0));
        assert_eq!(
            clamp(&Value::Vec2([-1.0, 0.5]), &Value::Float(0.0), &Value::Float(1.0)),
            Value::Vec2([0.0, 0.5])
        );
    }
}
