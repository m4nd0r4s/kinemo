//! Expression graph: derived values traced from Python and evaluated natively.

use serde::{Deserialize, Serialize};

use crate::{ObjectId, SignalId, Value};


#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum UnOp {
    Neg,
    Not,
    Abs,
    Sin,
    Cos,
    Tan,
    Exp,
    Ln,
    Sqrt,
    Floor,
    Ceil,
    Round,
    X,
    Y,
    Len,
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BinOp {
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Pow,
    Lt,
    Le,
    Gt,
    Ge,
    Eq,
    Ne,
    And,
    Or,
    Min,
    Max,
    Atan2,
}

/// Expression graph node. Acyclic by construction (derived values are read-only).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Expr {
    Const { v: Value },
    /// Read of a signal (free signal or object prop).
    Sig { id: SignalId },
    /// Global scene time `k.time`.
    Time,
    /// Time since an object entered the scene (`self.age`).
    Age { obj: ObjectId },
    /// Layout-derived read: x, y, width, height, left, right, top, bottom, center, position.
    Derived { obj: ObjectId, prop: String, #[serde(default)] world: bool },
    /// A point in an object's local coordinates, mapped to world coordinates.
    ToWorld { obj: ObjectId, p: Box<Expr> },
    Un { f: UnOp, a: Box<Expr> },
    Bin { f: BinOp, a: Box<Expr>, b: Box<Expr> },
    Where { c: Box<Expr>, a: Box<Expr>, b: Box<Expr> },
    Clamp { a: Box<Expr>, lo: Box<Expr>, hi: Box<Expr> },
    /// Mix of numbers, vectors or colors (colors in OKLab).
    Mix { a: Box<Expr>, b: Box<Expr>, t: Box<Expr> },
    Vec2 { x: Box<Expr>, y: Box<Expr> },
    /// Python format-spec applied to a value (`f"{x:.2f}"`).
    Format { spec: String, a: Box<Expr> },
    Concat { parts: Vec<Expr> },
    /// Piecewise-linear interpolation over a table.
    Interp { x: Box<Expr>, xs: Vec<f64>, ys: Vec<f64> },
    /// Natural cubic spline through `(xs[i], ys[i])` with second derivatives `m`.
    Spline { x: Box<Expr>, xs: Vec<f64>, ys: Vec<f64>, m: Vec<f64> },
    /// Precomputed table sampled on the frame grid (`k.python`, integrals, simulations).
    Table { table: u32 },
    /// Value-noise for organic motion.
    Noise { a: Box<Expr>, seed: u32 },
    /// Attribute of the symbolic point `p` of a per-point function (mass objects):
    /// `"x"`, `"y"`, `"index"`, `"count"` or `"t"` (normalized position `index / (count - 1)`).
    /// Evaluates to 0 outside a point context.
    Point { attr: String },
}

impl Expr {
    /// Whether this expression reads the point context (`Expr::Point`) anywhere.
    pub fn uses_point(&self) -> bool {
        let any = |es: &[&Expr]| es.iter().any(|e| e.uses_point());
        match self {
            Expr::Point { .. } => true,
            Expr::Const { .. } | Expr::Sig { .. } | Expr::Time | Expr::Age { .. } | Expr::Derived { .. } | Expr::Table { .. } => false,
            Expr::ToWorld { p, .. } => p.uses_point(),
            Expr::Un { a, .. } | Expr::Format { a, .. } | Expr::Noise { a, .. } => a.uses_point(),
            Expr::Interp { x, .. } | Expr::Spline { x, .. } => x.uses_point(),
            Expr::Bin { a, b, .. } => any(&[a, b]),
            Expr::Where { c, a, b } => any(&[c, a, b]),
            Expr::Clamp { a, lo, hi } => any(&[a, lo, hi]),
            Expr::Mix { a, b, t } => any(&[a, b, t]),
            Expr::Vec2 { x, y } => any(&[x, y]),
            Expr::Concat { parts } => parts.iter().any(Expr::uses_point),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn point_expr_roundtrip_and_detection() {
        let e = Expr::Mix {
            a: Box::new(Expr::Const { v: Value::Float(0.0) }),
            b: Box::new(Expr::Const { v: Value::Float(1.0) }),
            t: Box::new(Expr::Point { attr: "x".into() }),
        };
        let j = serde_json::to_string(&e).unwrap();
        assert!(j.contains(r#"{"op":"point","attr":"x"}"#));
        assert_eq!(serde_json::from_str::<Expr>(&j).unwrap(), e);
        assert!(e.uses_point());
        assert!(!Expr::Time.uses_point());
    }
}
