//! Resolve-phase analyses over a finished IR scene.
//!
//! Currently: timeline sampling ([`sampling`]) and the visual lints W10xx ([`lints`]),
//! which look at the scene the way a viewer would (frame by frame) and point at the
//! instant and the objects of each readability problem.

pub mod lints;
pub mod sampling;

pub use lints::{run_visual_lints, LintCode, LintDetails, LintFinding, LintOptions, SuggestedFix};
