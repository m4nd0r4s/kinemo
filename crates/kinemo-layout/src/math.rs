//! Math formulas as glyph sources (`k.Math`): glyphs and rules keyed by their TeX node.

use kurbo::Rect;

use kinemo_ir::ObjectId;
use kinemo_math::{layout_math, MathLayout, MathOptions};

use crate::glyphs::SourceGlyph;
use crate::Layout;

impl<'a> Layout<'a> {
    pub(crate) fn math_layout(&self, o: ObjectId, t: f64) -> Option<std::sync::Arc<MathLayout>> {
        let tex = self.prop_str(o, "tex", t).unwrap_or_default();
        let opts = MathOptions { size: self.prop_f(o, "size", t, 0.6), display: self.prop_bool(o, "display", t, true) };
        layout_math(&tex, &opts).ok()
    }

    /// Glyphs (then rules: fraction bars, radicals) with the normalized TeX of their node
    /// as key; `word` carries the node id for subexpression lookups.
    pub(crate) fn math_glyphs(&self, o: ObjectId, t: f64) -> Vec<SourceGlyph> {
        let Some(lay) = self.math_layout(o, t) else { return vec![] };
        let glyph = |i: usize, path: &kurbo::BezPath, node: usize| SourceGlyph {
            path: path.clone(),
            key: lay.parts.get(node).map(|p| p.tex.clone()).unwrap_or_default(),
            char_index: i,
            line: 0,
            word: node,
            color: None,
        };
        let mut out: Vec<SourceGlyph> = lay.glyphs.iter().enumerate().map(|(i, g)| glyph(i, &g.path, g.node)).collect();
        let offset = out.len();
        out.extend(lay.rules.iter().enumerate().map(|(i, (path, node))| glyph(offset + i, path, *node)));
        out
    }

    pub(crate) fn math_box(&self, o: ObjectId, t: f64) -> Rect {
        self.math_layout(o, t).map_or(Rect::ZERO, |l| l.bbox)
    }
}
