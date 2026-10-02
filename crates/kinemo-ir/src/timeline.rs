//! Signal timelines: sets, animations, easing and interpolation modes.

use serde::{Deserialize, Serialize};

use crate::{Expr, ObjectId, SignalId, Span, Value};

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
#[derive(Default)]
pub enum Ease {
    Linear,
    #[default]
    Smooth,
    In,
    Out,
    InOut,
    OutBack,
    OutElastic,
    Spring {
        stiffness: f64,
        damping: f64,
    },
    Steps {
        n: u32,
    },
    /// Sampled f:[0,1]→ℝ, evenly spaced.
    Table {
        ys: Vec<f64>,
    },
    /// Composition used by `with_`/reversal: ease(1-t) reversed.
    Reverse {
        inner: Box<Ease>,
    },
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum Blend {
    #[default]
    Replace,
    Add,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "k", rename_all = "snake_case")]
pub enum Src {
    Val { v: Value },
    Expr { e: Expr },
}

/// One change in a signal's timeline.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "k", rename_all = "snake_case")]
pub enum Entry {
    Set {
        t: f64,
        src: Src,
        #[serde(default)]
        span: Span,
    },
    Anim {
        t0: f64,
        t1: f64,
        /// Target value; an `Expr` target is live and becomes a binding once the animation ends.
        to: Src,
        /// Explicit start value; `None` = value of the signal at `t0`.
        #[serde(default)]
        from: Option<Src>,
        #[serde(default)]
        ease: Ease,
        #[serde(default)]
        blend: Blend,
        #[serde(default)]
        span: Span,
    },
}

impl Entry {
    pub fn start(&self) -> f64 {
        match self {
            Entry::Set { t, .. } => *t,
            Entry::Anim { t0, .. } => *t0,
        }
    }
    pub fn end(&self) -> f64 {
        match self {
            Entry::Set { t, .. } => *t,
            Entry::Anim { t1, .. } => *t1,
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum Lerp {
    /// Numeric interpolation (floats, vectors, colors in OKLab).
    #[default]
    Linear,
    /// Integer: linear then rounded.
    Round,
    /// Step at the end of the animation.
    StepEnd,
    /// Step at the start of the animation.
    StepStart,
    /// Point-by-point interpolation of lists of vectors (resampled).
    Pointwise,
    /// Lists of children: layout-level blend between the two arrangements.
    Layout,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Signal {
    pub id: SignalId,
    pub initial: Value,
    #[serde(default)]
    pub lerp: Lerp,
    #[serde(default)]
    pub timeline: Vec<Entry>,
    /// Owning object and prop name, if this is an object prop.
    #[serde(default)]
    pub owner: Option<(ObjectId, String)>,
    #[serde(default)]
    pub span: Span,
}
