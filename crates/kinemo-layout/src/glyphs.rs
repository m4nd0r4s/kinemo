//! Glyph sources (text, math, code) and glyph runs: addressable parts of a text.
//!
//! A text-like object is a group of `glyphs` parts selecting glyphs of the source by index.
//! `txt["world"]` is one part: a group holding a `rest` run (the leaf that draws) and the
//! parts addressed inside it (`txt.chars[0:2]` inside `txt.words[0]`). Every `rest` run
//! draws the glyphs of its owner that no sibling part claims, and when two sibling parts
//! overlap without one containing the other the later one draws the shared glyphs, so
//! styling parts never duplicates or loses glyphs.

use std::collections::HashSet;
use std::sync::Arc;

use kurbo::{Affine, Rect, Shape};
use kinemo_math::{layout_math, MathLayout, MathOptions};
use kinemo_text::{FontStyle, InlineBox, TextLayout};

use kinemo_ir::{ObjectId, Value};

use crate::geometry::{PartRole, ShapePart};
use crate::Layout;

/// One glyph of a source, in the source's local coordinates.
#[derive(Clone, Debug)]
pub struct SourceGlyph {
    pub path: kurbo::BezPath,
    pub key: String,
    pub char_index: usize,
    pub line: usize,
    pub word: usize,
    pub color: Option<[f64; 4]>,
}

/// A text laid out with its `$math$` spans (see [`Layout::text_with_math`]).
struct InlineText {
    layout: Arc<TextLayout>,
    /// The typeset spans, in order; empty when they stay literal.
    math: Vec<Arc<MathLayout>>,
    /// TeX of each span.
    spans: Vec<String>,
}

impl<'a> Layout<'a> {
    /// Glyphs of a text-like source object (`text`, `code`) at `t`.
    pub fn source_glyphs(&self, source: ObjectId, t: f64) -> Vec<SourceGlyph> {
        match self.scene().object(source).kind.as_str() {
            "code" => return self.code_glyphs(source, t),
            "math" => return self.math_glyphs(source, t),
            _ => {}
        }
        let text = self.text_with_math(source, t);
        let chars: Vec<char> = text.layout.plain.chars().collect();
        let mut out = Vec::with_capacity(text.layout.glyphs.len());
        let mut span = 0;
        for g in &text.layout.glyphs {
            if g.style == FontStyle::Inline {
                // A `$math$` span: the formula's glyphs and rules, on the text's baseline, all
                // keyed by the span's TeX so `txt["f'(x)"]` finds them.
                if let Some(math) = text.math.get(span) {
                    let r = g.advance_rect;
                    let baseline = r.y0 + (math.baseline - math.bbox.y0);
                    let shift = Affine::translate((r.x0 - math.bbox.x0, baseline - math.baseline));
                    let paths = math.glyphs.iter().map(|m| &m.path).chain(math.rules.iter().map(|(path, _)| path));
                    out.extend(paths.map(|path| SourceGlyph {
                        path: shift * path.clone(),
                        key: text.spans[span].clone(),
                        char_index: g.char_index,
                        line: g.line,
                        word: g.word,
                        color: None,
                    }));
                }
                span += 1;
                continue;
            }
            out.push(SourceGlyph {
                path: g.path.clone(),
                key: chars.get(g.char_index).map(|c| c.to_string()).unwrap_or_default(),
                char_index: g.char_index,
                line: g.line,
                word: g.word,
                color: None,
            });
        }
        out
    }

    /// A text's layout with its `$math$` spans typeset inline: each span takes a box the size
    /// of its formula on the line. When a span does not typeset, all stay literal text (the
    /// Python side reports the TeX error when the text is made).
    fn text_with_math(&self, source: ObjectId, t: f64) -> InlineText {
        let text = self.prop_str(source, "text", t).unwrap_or_default();
        let mut opts = self.text_options(source, t);
        let spans = kinemo_text::math_spans(&text, &opts);
        let laid: Vec<Option<Arc<MathLayout>>> = spans.iter().map(|tex| layout_math(tex, &MathOptions { size: opts.size, display: false }).ok()).collect();
        let math: Vec<Arc<MathLayout>> = if laid.iter().all(Option::is_some) { laid.into_iter().flatten().collect() } else { Vec::new() };
        opts.inline = math.iter().map(|m| InlineBox { width: m.bbox.width(), ascent: m.bbox.y1 - m.baseline, descent: m.baseline - m.bbox.y0 }).collect();
        InlineText { layout: kinemo_text::layout(&text, &opts), math, spans }
    }

    /// Number of glyphs of a source (what [`Layout::source_glyphs`] returns), without
    /// copying their outlines.
    pub fn source_glyph_count(&self, source: ObjectId, t: f64) -> usize {
        match self.scene().object(source).kind.as_str() {
            "code" => self.code_layout(source, t).map_or(0, |lay| lay.glyphs.len() + lay.line_numbers.iter().map(Vec::len).sum::<usize>()),
            "math" => self.math_layout(source, t).map_or(0, |lay| lay.glyphs.len() + lay.rules.len()),
            _ => {
                let text = self.text_with_math(source, t);
                let inline = text.layout.glyphs.iter().filter(|g| g.style == FontStyle::Inline).count();
                text.layout.glyphs.len() - inline + text.math.iter().map(|m| m.glyphs.len() + m.rules.len()).sum::<usize>()
            }
        }
    }

    /// Logical box of a source (the text block, not the ink).
    pub fn source_box(&self, source: ObjectId, t: f64) -> Rect {
        match self.scene().object(source).kind.as_str() {
            "code" => return self.code_box(source, t),
            "math" => return self.math_box(source, t),
            _ => {}
        }
        self.text_with_math(source, t).layout.bbox
    }

    /// Drawable glyphs of a source, optionally restricted to `selected` indices.
    pub(crate) fn source_parts(&self, source: ObjectId, t: f64, selected: Option<&HashSet<usize>>) -> Vec<ShapePart> {
        let glyphs = self.source_glyphs(source, t);
        let count = glyphs.len();
        glyphs
            .into_iter()
            .enumerate()
            .filter(|(i, _)| selected.is_none_or(|s| s.contains(i)))
            .map(|(i, g)| ShapePart { path: g.path, role: PartRole::Glyph, index: i, count, key: Some(g.key), color: g.color })
            .collect()
    }

    /// The text-like object a run or part selects from: its first ancestor that is not a part.
    fn run_source(&self, run: ObjectId, t: f64) -> Option<ObjectId> {
        if let Some(Value::Object(id)) = self.prop(run, "source", t) {
            return Some(id);
        }
        let mut current = self.scene().object(run).parent;
        while let Some(id) = current {
            if self.scene().object(id).kind != "glyphs" {
                return Some(id);
            }
            current = self.scene().object(id).parent;
        }
        None
    }

    fn run_indices(&self, run: ObjectId, t: f64) -> HashSet<usize> {
        self.prop(run, "indices", t)
            .map(|v| v.as_list().iter().map(|i| i.as_f64() as usize).collect())
            .unwrap_or_default()
    }

    fn is_part(&self, o: ObjectId, t: f64) -> bool {
        self.scene().object(o).kind == "glyphs" && !self.prop_bool(o, "rest", t, false)
    }

    /// Glyphs a part (or the text itself) actually owns: its selection, within its owner's,
    /// minus what later sibling parts claim.
    fn owned_indices(&self, owner: ObjectId, source: ObjectId, t: f64) -> HashSet<usize> {
        if !self.is_part(owner, t) {
            return (0..self.source_glyph_count(source, t)).collect();
        }
        let mut own = self.run_indices(owner, t);
        if let Some(parent) = self.scene().object(owner).parent {
            let inherited = self.owned_indices(parent, source, t);
            own.retain(|i| inherited.contains(i));
            let siblings = self.children(parent, t);
            let position = siblings.iter().position(|&c| c == owner).unwrap_or(siblings.len());
            for &later in siblings.iter().skip(position + 1) {
                if self.is_part(later, t) {
                    for i in self.run_indices(later, t) {
                        own.remove(&i);
                    }
                }
            }
        }
        own
    }

    /// Indices drawn by a run: its own selection (a leaf part from older scenes), or for a
    /// `rest` run what its owner owns and no part inside the owner claims.
    pub fn run_selection(&self, run: ObjectId, t: f64) -> HashSet<usize> {
        let Some(source) = self.run_source(run, t) else { return HashSet::new() };
        let Some(owner) = self.scene().object(run).parent else { return HashSet::new() };
        if !self.prop_bool(run, "rest", t, false) {
            let owned = self.owned_indices(owner, source, t);
            return self.run_indices(run, t).into_iter().filter(|i| owned.contains(i)).collect();
        }
        let mut selection = self.owned_indices(owner, source, t);
        for sibling in self.children(owner, t) {
            if sibling != run && self.is_part(sibling, t) {
                for i in self.run_indices(sibling, t) {
                    selection.remove(&i);
                }
            }
        }
        selection
    }

    pub(crate) fn glyph_run_parts(&self, run: ObjectId, t: f64) -> Vec<ShapePart> {
        let Some(source) = self.run_source(run, t) else { return vec![] };
        let selection = self.run_selection(run, t);
        self.source_parts(source, t, Some(&selection))
    }

    /// Box of a run: the whole logical block for the text's `rest` run (so alignment does
    /// not depend on which parts were split off); for the `rest` run of a part, the ink of
    /// every glyph the part selects (a stable pivot while inner parts move); the ink of its
    /// glyphs otherwise.
    pub(crate) fn glyph_run_box(&self, run: ObjectId, t: f64) -> Rect {
        let Some(source) = self.run_source(run, t) else { return Rect::ZERO };
        let owner = self.scene().object(run).parent;
        let rest = self.prop_bool(run, "rest", t, false);
        let selection = match owner {
            Some(part) if rest && self.is_part(part, t) => self.run_indices(part, t),
            _ if rest => return self.source_box(source, t),
            _ => self.run_selection(run, t),
        };
        self.source_parts(source, t, Some(&selection))
            .iter()
            .map(|p| p.path.bounding_box())
            .reduce(|a, b| a.union(b))
            .unwrap_or(Rect::ZERO)
    }
}
