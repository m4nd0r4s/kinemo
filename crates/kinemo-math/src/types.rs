//! Public data types: options and layout results.

use kurbo::{BezPath, Rect};

/// Options for [`crate::layout_math`].
#[derive(Clone, Debug, PartialEq)]
pub struct MathOptions {
    /// Font size = em height, in scene units.
    pub size: f64,
    /// Display style (`\[...\]`) when true, inline style (`$...$`) when false.
    pub display: bool,
}

impl Default for MathOptions {
    fn default() -> Self {
        MathOptions { size: 0.5, display: true }
    }
}

/// One glyph outline of a laid-out formula.
#[derive(Clone, Debug)]
pub struct MathGlyph {
    /// Filled outline in scene units, y-up; the formula block is centered at (0,0).
    pub path: BezPath,
    /// Innermost part-tree node (index into [`MathLayout::parts`]) the glyph comes from.
    pub node: usize,
}

/// A node of the part tree: one TeX subexpression.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PartNode {
    pub parent: Option<usize>,
    /// Name given with `\id{name}{...}`.
    pub name: Option<String>,
    /// Normalized TeX of this subtree (e.g. `"c^{2}"`), as compared by [`crate::find`].
    pub tex: String,
    pub children: Vec<usize>,
}

/// A laid-out formula.
#[derive(Clone, Debug)]
pub struct MathLayout {
    /// Visible glyphs, in typst's paint order.
    pub glyphs: Vec<MathGlyph>,
    /// Non-glyph ink (fraction bars, radical overlines, `\overline`, `\cancel`, `\boxed`
    /// frames...) as filled paths, each with its innermost part-tree node.
    pub rules: Vec<(BezPath, usize)>,
    /// Part tree; index 0 is the root (the whole formula).
    pub parts: Vec<PartNode>,
    /// Logical box (typst's frame), centered at (0,0), y-up.
    pub bbox: Rect,
}
