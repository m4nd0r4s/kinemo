//! Glyph sources (text, math, code) and glyph runs: addressable parts of a text.
//!
//! A text-like object is a group whose leaves are `glyphs` runs selecting glyphs of the
//! source by index. `txt["world"]` is one run; the `rest` run draws every glyph no
//! sibling run claims, so styling a part never duplicates or loses glyphs.

use std::collections::HashSet;

use kurbo::{Rect, Shape};

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

impl<'a> Layout<'a> {
    /// Glyphs of a text-like source object (`text`, `code`) at `t`.
    pub fn source_glyphs(&self, source: ObjectId, t: f64) -> Vec<SourceGlyph> {
        match self.scene().object(source).kind.as_str() {
            "code" => return self.code_glyphs(source, t),
            "math" => return self.math_glyphs(source, t),
            _ => {}
        }
        let text = self.prop_str(source, "text", t).unwrap_or_default();
        let lay = kinemo_text::layout(&text, &self.text_options(source, t));
        let chars: Vec<char> = lay.plain.chars().collect();
        lay.glyphs
            .iter()
            .map(|g| SourceGlyph {
                path: g.path.clone(),
                key: chars.get(g.char_index).map(|c| c.to_string()).unwrap_or_default(),
                char_index: g.char_index,
                line: g.line,
                word: g.word,
                color: None,
            })
            .collect()
    }

    /// Logical box of a source (the text block, not the ink).
    pub fn source_box(&self, source: ObjectId, t: f64) -> Rect {
        match self.scene().object(source).kind.as_str() {
            "code" => return self.code_box(source, t),
            "math" => return self.math_box(source, t),
            _ => {}
        }
        let text = self.prop_str(source, "text", t).unwrap_or_default();
        kinemo_text::measure(&text, &self.text_options(source, t))
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

    fn run_source(&self, run: ObjectId, t: f64) -> Option<ObjectId> {
        match self.prop(run, "source", t) {
            Some(Value::Object(id)) => Some(id),
            _ => self.scene().object(run).parent,
        }
    }

    fn run_indices(&self, run: ObjectId, t: f64) -> HashSet<usize> {
        self.prop(run, "indices", t)
            .map(|v| v.as_list().iter().map(|i| i.as_f64() as usize).collect())
            .unwrap_or_default()
    }

    /// Indices drawn by a run: its own selection, or (for the `rest` run) everything its
    /// sibling runs do not claim.
    pub fn run_selection(&self, run: ObjectId, t: f64) -> HashSet<usize> {
        if !self.prop_bool(run, "rest", t, false) {
            return self.run_indices(run, t);
        }
        let Some(source) = self.run_source(run, t) else { return HashSet::new() };
        let mut claimed = HashSet::new();
        if let Some(parent) = self.scene().object(run).parent {
            for sibling in self.children(parent, t) {
                if sibling != run && self.scene().object(sibling).kind == "glyphs" && !self.prop_bool(sibling, "rest", t, false) {
                    claimed.extend(self.run_indices(sibling, t));
                }
            }
        }
        (0..self.source_glyphs(source, t).len()).filter(|i| !claimed.contains(i)).collect()
    }

    pub(crate) fn glyph_run_parts(&self, run: ObjectId, t: f64) -> Vec<ShapePart> {
        let Some(source) = self.run_source(run, t) else { return vec![] };
        let selection = self.run_selection(run, t);
        self.source_parts(source, t, Some(&selection))
    }

    /// Box of a run: the whole logical block for the `rest` run (so alignment does not
    /// depend on which parts were split off), the ink of its glyphs otherwise.
    pub(crate) fn glyph_run_box(&self, run: ObjectId, t: f64) -> Rect {
        let Some(source) = self.run_source(run, t) else { return Rect::ZERO };
        if self.prop_bool(run, "rest", t, false) {
            return self.source_box(source, t);
        }
        self.glyph_run_parts(run, t)
            .iter()
            .map(|p| p.path.bounding_box())
            .reduce(|a, b| a.union(b))
            .unwrap_or(Rect::ZERO)
    }
}
