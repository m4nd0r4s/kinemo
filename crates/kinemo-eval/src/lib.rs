//! kinemo-eval: pure evaluation of the kinemo IR.
//!
//! Given a [`kinemo_ir::Scene`], the [`Evaluator`] answers the value of any
//! signal or expression at any time, applying timeline semantics (sets,
//! replace/additive animations, reactive bindings), easing and typed
//! interpolation. Layout-derived reads are delegated to a [`Resolver`].
//!
//! Modules:
//! * [`ease`] — easing curves.
//! * [`color`] — sRGB ↔ OKLab and perceptual mixing.
//! * [`format`] — Python format-spec subset for `f"{x:.2f}"`.
//! * [`interp`] — interpolation by [`kinemo_ir::Lerp`] mode.
//! * [`noise`] — deterministic value noise.
//! * `evaluator` — timeline walking, expression evaluation, memoization, and
//!   per-point evaluation ([`PointContext`]) for mass objects.

pub mod color;
pub mod ease;
mod evaluator;
pub mod format;
pub mod interp;
pub mod noise;

pub use evaluator::{Evaluated, Evaluator, NoResolver, PointContext, PointSource, Resolver, TimelineIndex};
