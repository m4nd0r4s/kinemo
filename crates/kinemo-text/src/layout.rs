//! Assembling a `TextLayout`: markup -> shaping -> line breaking -> positioning.

use kurbo::{Point, Rect};

use crate::fonts::line_metrics;
use crate::types::{Align, Glyph, TextLayout, TextOptions};
use crate::{markup, outline, shape, wrap};

/// Uncached layout. The logical bbox is centered at (0,0).
pub(crate) fn compute(text: &str, opts: &TextOptions) -> TextLayout {
    let styled = markup::parse(text, opts);
    let chars: Vec<char> = styled.iter().map(|(c, _)| *c).collect();
    let plain: String = chars.iter().collect();
    let n = chars.len();

    let (words, word_of) = wrap::words(&chars);
    let shaped = shape::shape_all(&styled, opts);

    let mut char_adv = vec![0.0f64; n];
    for g in &shaped {
        char_adv[g.char_index] += g.advance;
    }

    let line_ranges = wrap::break_lines(&chars, &char_adv, opts.width);
    let widths: Vec<f64> = line_ranges.iter().map(|&r| wrap::line_width(&chars, &char_adv, r)).collect();

    let (ascender, descender) = line_metrics(opts.size);
    let lh = opts.line_height * opts.size;
    let max_w = widths.iter().cloned().fold(0.0, f64::max);
    let total_h = line_ranges.len().max(1) as f64 * lh;
    // Offset that centers the block (built with its top-left at the origin).
    let (dx, dy) = (-max_w / 2.0, total_h / 2.0);

    let mut line_of = vec![usize::MAX; n];
    for (li, &(s, e)) in line_ranges.iter().enumerate() {
        line_of[s..e].fill(li);
    }

    let x0s: Vec<f64> = widths
        .iter()
        .map(|&w| match opts.align {
            Align::Left => 0.0,
            Align::Center => (max_w - w) / 2.0,
            Align::Right => max_w - w,
        })
        .collect();
    let lines: Vec<Rect> = widths
        .iter()
        .zip(&x0s)
        .enumerate()
        .map(|(li, (&w, &x0))| {
            let top = -(li as f64) * lh + dy;
            Rect::new(x0 + dx, top - lh, x0 + w + dx, top)
        })
        .collect();

    let mut pens = x0s;
    let mut glyphs = Vec::with_capacity(shaped.len());
    for g in &shaped {
        let li = line_of[g.char_index];
        if li == usize::MAX {
            continue; // whitespace swallowed at a wrap point
        }
        let pen = pens[li];
        pens[li] += g.advance;
        if chars[g.char_index].is_whitespace() {
            continue;
        }
        let baseline = -(li as f64) * lh - ascender + dy;
        let x = pen + dx;
        let origin = Point::new(x + g.x_off, baseline + g.y_off);
        glyphs.push(Glyph {
            path: outline::glyph_path(g.style, g.gid, opts.size, origin),
            char_index: g.char_index,
            line: li,
            word: word_of[g.char_index],
            advance_rect: Rect::new(x, baseline + descender, x + g.advance, baseline + ascender),
            style: g.style,
        });
    }

    TextLayout {
        plain,
        glyphs,
        bbox: Rect::new(-max_w / 2.0, -total_h / 2.0, max_w / 2.0, total_h / 2.0),
        lines,
        words,
    }
}
