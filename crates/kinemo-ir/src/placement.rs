//! Layout constraints declared with `.place(...)`.

use serde::{Deserialize, Serialize};

use crate::{Ease, Expr, ObjectId, Span};


#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Side {
    Above,
    Below,
    LeftOf,
    RightOf,
    Inside,
}

/// A layout constraint. `None` axes are free (driven by x/y signals).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Placement {
    /// Frame anchor ("center", "top-left", ...), relative to the frame.
    #[serde(default)]
    pub at: Option<String>,
    /// Absolute point (in parent coordinates) for `at=(x, y)` or `at=obj.point`.
    #[serde(default)]
    pub at_point: Option<Expr>,
    #[serde(default)]
    pub side: Option<Side>,
    #[serde(default)]
    pub target: Option<ObjectId>,
    #[serde(default)]
    pub gap: Option<Expr>,
    #[serde(default)]
    pub margin: Option<Expr>,
    #[serde(default)]
    pub align: Option<String>,
    #[serde(default)]
    pub clamp: bool,
    #[serde(default)]
    pub weak: bool,
    #[serde(default)]
    pub rotated: bool,
    #[serde(default)]
    pub span: Span,
}

/// Placement timeline entry: from `t` on, the object follows `p` (or is free if `None`),
/// blending from the previous placement over `dur` seconds.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct PlaceEntry {
    pub t: f64,
    #[serde(default)]
    pub dur: f64,
    #[serde(default)]
    pub ease: Ease,
    pub p: Option<Placement>,
    /// The `.place(...)` / `.to_place(...)` / `.unpin()` call that set it.
    #[serde(default)]
    pub span: Span,
}
