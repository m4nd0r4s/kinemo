//! Geometry and layout of the scene graph at a given time.
//!
//! [`Layout`] answers "where is everything at t": local geometry of each node,
//! container arrangement (`Row`, `Column`, `Grid`, `Stack`), relative constraints
//! (`place(...)`) and the resulting transforms. It also implements the evaluator's
//! [`kinemo_eval::Resolver`], so expressions can read layout-derived props
//! (`obj.left`, `obj.width`, ...).

mod brace;
mod code;
mod container;
mod diag;
mod engine;
mod geometry;
mod math;
mod glyphs;
pub mod mass;
mod place;
mod plot;
mod props;
mod trail;
mod transform;

pub use diag::{LayoutIssue, LayoutIssueKind};
pub use engine::Layout;
pub use geometry::{PartRole, ShapePart};
pub use glyphs::SourceGlyph;
pub use transform::{anchor_point, frame_rect};
