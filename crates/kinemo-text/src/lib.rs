//! Text layout for kinemo (`k.Text`).
//!
//! Pipeline: `markup` parsing -> `shape` (rustybuzz, kerning, `tnum`) ->
//! `wrap` (greedy line breaking) -> `layout` (positioning, outlines via
//! `outline`) -> `cache`. Only the bundled DejaVu fonts (`fonts`) are
//! used, so results are deterministic across machines.
//!
//! Coordinates are scene units, y-up; a layout's logical bbox is centered at
//! the origin.

mod cache;
mod fonts;
mod layout;
mod markup;
mod outline;
mod query;
pub mod recent;
mod shape;
mod types;
mod wrap;

pub use cache::{layout, measure};
pub use query::ranges_of;
pub use types::{Align, FontStyle, Glyph, TextLayout, TextOptions};
