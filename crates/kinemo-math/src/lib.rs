//! LaTeX math layout for kinemo (`k.Math`), without any TeX installation.
//!
//! Pipeline: `latex_parser` (structure + `\id{name}{...}`) → `parts` (part tree,
//! each node wrapped in a color marker) → `convert` (mitex LaTeX→typst, with the
//! `command_spec` and the `mitex_prelude.typ` definitions) → `world` (typst
//! compile with the embedded New Computer Modern fonts) → `layout` (frame walk:
//! glyph outlines and rules, attributed to nodes by marker color) → `cache`.
//!
//! Coordinates are scene units, y-up; a layout's logical bbox is centered at
//! the origin. Subexpressions are looked up by syntax tree with [`find`]
//! (`c^2` ≡ `c^{2}`) or by name with [`named`].

pub mod baked;
mod cache;
mod command_spec;
#[cfg(feature = "typeset")]
mod convert;
mod error;
mod ast;
mod latex_parser;
mod latex_scanner;
#[cfg(feature = "typeset")]
mod layout;
mod normalize;
#[cfg(feature = "typeset")]
mod outline;
#[cfg(feature = "typeset")]
mod parts;
#[cfg(feature = "typeset")]
mod pipeline;
mod query;
#[cfg(feature = "typeset")]
mod typst_rename;
mod types;
#[cfg(feature = "typeset")]
mod world;

pub use cache::layout_math;
pub use error::MathError;
pub use query::{find, glyphs_of, named, normalize_tex, rules_of};
pub use types::{MathGlyph, MathLayout, MathOptions, PartNode};

/// Uncached layout with part markers disabled (every glyph maps to the root).
/// Only for verifying that markers do not change the layout.
#[cfg(feature = "typeset")]
#[doc(hidden)]
pub fn layout_math_without_markers(tex: &str, opts: &MathOptions) -> Result<MathLayout, MathError> {
    pipeline::compute_with_markers(tex, opts, false)
}

/// The typst document generated for `tex` (debugging aid).
#[cfg(feature = "typeset")]
#[doc(hidden)]
pub fn debug_typst_document(tex: &str, opts: &MathOptions) -> Result<String, MathError> {
    let tree = parts::build(&latex_parser::parse(tex)?, true);
    let math = convert::latex_to_typst(&tree.latex)?;
    Ok(convert::typst_document(&math, opts.display))
}
