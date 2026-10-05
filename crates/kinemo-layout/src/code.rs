//! Code blocks as glyph sources: syntax colors per token, line numbers, line highlight.

use kurbo::Rect;

use kinemo_code::{layout_code, CodeOptions, Palette};
use kinemo_ir::ObjectId;

use crate::glyphs::SourceGlyph;
use crate::Layout;

/// Alpha kept by lines outside the highlighted set at full highlight.
const DIMMED: f64 = 0.3;

impl<'a> Layout<'a> {
    fn code_options(&self, o: ObjectId, t: f64) -> CodeOptions {
        CodeOptions {
            size: self.prop_f(o, "size", t, 0.32),
            line_numbers: self.prop_bool(o, "line_numbers", t, false),
            ..CodeOptions::default()
        }
    }

    pub(crate) fn code_layout(&self, o: ObjectId, t: f64) -> Option<std::sync::Arc<kinemo_code::CodeLayout>> {
        let src = self.prop_str(o, "code", t).unwrap_or_default();
        let lang = self.prop_str(o, "lang", t).unwrap_or_else(|| "text".into());
        let options = self.code_options(o, t);
        // `k.Code` rejects unknown languages; one set later (a signal) shows as plain text
        // rather than nothing.
        layout_code(&src, &lang, &options).or_else(|_| layout_code(&src, "text", &options)).ok()
    }

    fn palette(&self, o: ObjectId, t: f64) -> Palette {
        match self.prop_str(o, "palette", t).as_deref() {
            Some("light") => Palette::light(),
            _ => Palette::dark(),
        }
    }

    /// Alpha factor of line `line` (0-based) under the current highlight.
    fn line_alpha(&self, o: ObjectId, line: usize, t: f64) -> f64 {
        let amount = self.prop_f(o, "highlight_amount", t, 0.0);
        if amount <= 0.0 {
            return 1.0;
        }
        let lines: Vec<usize> = self
            .prop(o, "highlight", t)
            .map(|v| v.as_list().iter().map(|x| x.as_f64() as usize).collect())
            .unwrap_or_default();
        if lines.contains(&(line + 1)) {
            1.0
        } else {
            1.0 - (1.0 - DIMMED) * amount
        }
    }

    pub(crate) fn code_glyphs(&self, o: ObjectId, t: f64) -> Vec<SourceGlyph> {
        let Some(lay) = self.code_layout(o, t) else { return vec![] };
        let palette = self.palette(o, t);
        let mut out: Vec<SourceGlyph> = lay
            .glyphs
            .iter()
            .map(|g| {
                let token = &lay.tokens[g.token];
                let [r, gr, b, a] = palette.color(token.kind);
                SourceGlyph {
                    path: g.path.clone(),
                    key: token.text.clone(),
                    char_index: g.char_index,
                    line: g.line,
                    word: g.token,
                    color: Some([r, gr, b, a * self.line_alpha(o, g.line, t)]),
                }
            })
            .collect();
        let [r, g, b, a] = palette.line_number;
        for (line, digits) in lay.line_numbers.iter().enumerate() {
            for path in digits {
                out.push(SourceGlyph {
                    path: path.clone(),
                    key: format!("#{}", line + 1),
                    char_index: usize::MAX,
                    line,
                    word: usize::MAX,
                    color: Some([r, g, b, a * self.line_alpha(o, line, t)]),
                });
            }
        }
        out
    }

    pub(crate) fn code_box(&self, o: ObjectId, t: f64) -> Rect {
        self.code_layout(o, t).map_or(Rect::ZERO, |l| l.bbox)
    }
}
