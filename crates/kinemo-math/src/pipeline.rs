//! The uncached pipeline: parse → part tree with markers → mitex → typst → ink.

use crate::convert::MAX_MARKERS;
use crate::convert::{latex_to_typst, typst_document};
use crate::error::MathError;
use crate::types::{MathLayout, MathOptions};
use crate::{latex_parser, layout, parts, world};

/// Lay out `tex` without caching.
pub(crate) fn compute(tex: &str, opts: &MathOptions) -> Result<MathLayout, MathError> {
    compute_with_markers(tex, opts, true)
}

/// Lay out `tex`; with `markers = false` no part markers are emitted, so every
/// glyph maps to the root (used to check that markers do not move glyphs).
pub(crate) fn compute_with_markers(tex: &str, opts: &MathOptions, markers: bool) -> Result<MathLayout, MathError> {
    let ast = latex_parser::parse(tex)?;
    let mut tree = parts::build(&ast, markers);
    if tree.parts.len() > MAX_MARKERS + 1 {
        tree = parts::build(&ast, false);
    }
    let math = latex_to_typst(&tree.latex)?;
    let document = typst_document(&math, opts.display);
    let frame = world::compile_first_page(&document).map_err(MathError::Layout)?;
    let mut ink = layout::collect(&frame, opts.size, tree.parts.len());
    for (glyph, is_prime) in ink.glyphs.iter_mut().zip(&ink.is_prime) {
        if let Some(&(_, script)) = tree.prime_bases.iter().find(|(base, _)| *is_prime && *base == glyph.node) {
            glyph.node = script;
        }
    }
    Ok(MathLayout { glyphs: ink.glyphs, rules: ink.rules, parts: tree.parts, bbox: ink.bbox })
}
