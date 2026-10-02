//! Shaping of style runs with rustybuzz.

use rustybuzz::ttf_parser::Tag;

use crate::fonts::{fonts, scale};
use crate::types::{FontStyle, TextOptions};

/// One shaped glyph, in scene units, before line positioning.
pub(crate) struct Shaped {
    pub gid: u16,
    pub style: FontStyle,
    /// Absolute char index (into the plain text) of the cluster start.
    pub char_index: usize,
    pub advance: f64,
    pub x_off: f64,
    pub y_off: f64,
}

/// Shape `text` (a single-style run starting at char `first_char` of the plain
/// text) and append the glyphs to `out`. Kerning is on; `tnum` when requested.
pub(crate) fn shape_run(text: &str, first_char: usize, style: FontStyle, opts: &TextOptions, out: &mut Vec<Shaped>) {
    if text.is_empty() {
        return;
    }
    let face = fonts().get(style);
    let s = scale(face, opts.size);
    let mut buf = rustybuzz::UnicodeBuffer::new();
    buf.push_str(text);
    buf.guess_segment_properties();
    let mut features = vec![rustybuzz::Feature::new(Tag::from_bytes(b"kern"), 1, ..)];
    if opts.tabular_nums {
        features.push(rustybuzz::Feature::new(Tag::from_bytes(b"tnum"), 1, ..));
    }
    let gb = rustybuzz::shape(face, &features, buf);
    let mut byte_to_char = vec![0usize; text.len() + 1];
    for (ci, (bi, _)) in text.char_indices().enumerate() {
        byte_to_char[bi] = ci;
    }
    for (info, pos) in gb.glyph_infos().iter().zip(gb.glyph_positions()) {
        out.push(Shaped {
            gid: info.glyph_id as u16,
            style,
            char_index: first_char + byte_to_char[info.cluster as usize],
            advance: pos.x_advance as f64 * s,
            x_off: pos.x_offset as f64 * s,
            y_off: pos.y_offset as f64 * s,
        });
    }
}

/// Shape all style runs of `styled` (runs never cross '\n').
pub(crate) fn shape_all(styled: &[(char, FontStyle)], opts: &TextOptions) -> Vec<Shaped> {
    let mut out = Vec::new();
    let n = styled.len();
    let mut i = 0;
    while i < n {
        if styled[i].0 == '\n' {
            i += 1;
            continue;
        }
        let st = styled[i].1;
        let s = i;
        while i < n && styled[i].0 != '\n' && styled[i].1 == st {
            i += 1;
        }
        let run: String = styled[s..i].iter().map(|(c, _)| *c).collect();
        shape_run(&run, s, st, opts, &mut out);
    }
    out
}
