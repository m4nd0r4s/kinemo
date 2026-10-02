//! Public-API tests for kinemo-text. Nothing is written to disk.

use std::sync::Arc;

use kinemo_text::{layout, measure, ranges_of, Align, FontStyle, TextOptions};

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-9
}

#[test]
fn bbox_is_centered() {
    let l = layout("Hello world", &TextOptions::default());
    assert!(approx(l.bbox.center().x, 0.0));
    assert!(approx(l.bbox.center().y, 0.0));
    assert!(l.bbox.width() > 0.0);
    assert!(approx(l.bbox.height(), 0.5 * 1.25));
    assert_eq!(measure("Hello world", &TextOptions::default()), l.bbox);
    for g in &l.glyphs {
        assert!(!g.path.elements().is_empty());
    }
}

#[test]
fn wrap_creates_lines() {
    let text = "the quick brown fox jumps over the lazy dog";
    assert_eq!(layout(text, &TextOptions::default()).lines.len(), 1);
    let l = layout(text, &TextOptions { width: Some(2.0), ..Default::default() });
    assert!(l.lines.len() > 1, "lines = {}", l.lines.len());
    assert!(l.bbox.width() <= 2.0 + 1e-9);
    assert!(approx(l.bbox.height(), l.lines.len() as f64 * 0.625));
    assert!(approx(l.bbox.center().y, 0.0));
    for w in l.lines.windows(2) {
        assert!(w[1].y1 <= w[0].y0 + 1e-9, "lines go downwards");
    }
    for g in &l.glyphs {
        assert!(l.glyphs.iter().filter(|h| h.word == g.word).all(|h| h.line == g.line));
    }
    assert_eq!(layout("a\nb\n\nc", &TextOptions::default()).lines.len(), 4);
    let long = layout("supercalifragilistic", &TextOptions { width: Some(0.5), ..Default::default() });
    assert_eq!(long.lines.len(), 1, "a single long word overflows");
}

#[test]
fn markup_stripping_and_styles() {
    let l = layout("Café **world**, *look* `code` $x^2$ \\*lit\\*", &TextOptions::default());
    assert_eq!(l.plain, "Café world, look code $x^2$ *lit*");
    let style_at = |ci: usize| l.glyphs.iter().find(|g| g.char_index == ci).unwrap().style;
    assert_eq!(style_at(0), FontStyle::Regular);
    assert_eq!(style_at(5), FontStyle::Bold);
    assert_eq!(style_at(12), FontStyle::Italic);
    assert_eq!(style_at(17), FontStyle::Mono);
    assert_eq!(style_at(22), FontStyle::Regular);
    let raw = layout("**a**", &TextOptions { markup: false, ..Default::default() });
    assert_eq!(raw.plain, "**a**");
    let m = layout("ab", &TextOptions { mono: true, ..Default::default() });
    assert!(m.glyphs.iter().all(|g| g.style == FontStyle::Mono));
}

#[test]
fn char_indices_words_lines() {
    let l = layout("ab cd\nef", &TextOptions::default());
    let idx: Vec<usize> = l.glyphs.iter().map(|g| g.char_index).collect();
    assert_eq!(idx, vec![0, 1, 3, 4, 6, 7]);
    let words: Vec<usize> = l.glyphs.iter().map(|g| g.word).collect();
    assert_eq!(words, vec![0, 0, 1, 1, 2, 2]);
    let lines: Vec<usize> = l.glyphs.iter().map(|g| g.line).collect();
    assert_eq!(lines, vec![0, 0, 0, 0, 1, 1]);
    assert_eq!(l.words, vec![(0, 2), (3, 5), (6, 8)]);
    assert!(l.glyphs[1].advance_rect.x0 >= l.glyphs[0].advance_rect.x1 - 1e-9);
}

#[test]
fn tabular_digits() {
    let o = TextOptions::default();
    assert!(approx(measure("111", &o).width(), measure("888", &o).width()));
    assert!(approx(measure("12.5 kWh", &o).width(), measure("98.0 kWh", &o).width()));
}

#[test]
fn alignment() {
    let l = layout("long line here\nx", &TextOptions { align: Align::Right, ..Default::default() });
    assert!(approx(l.lines[0].x1, l.lines[1].x1));
    let l = layout("long line here\nx", &TextOptions { align: Align::Center, ..Default::default() });
    assert!(approx(l.lines[1].center().x, 0.0));
}

#[test]
fn ranges() {
    assert_eq!(ranges_of("café world, world", "world"), vec![(5, 10), (12, 17)]);
    assert_eq!(ranges_of("aaaa", "aa"), vec![(0, 2), (2, 4)]);
    assert_eq!(ranges_of("abc", ""), vec![]);
    assert_eq!(ranges_of("abc", "x"), vec![]);
}

#[test]
fn deterministic_and_cached() {
    let o = TextOptions::default();
    let a = layout("cache me", &o);
    assert!(Arc::ptr_eq(&a, &layout("cache me", &o)));
    // A different cache key that yields the same geometry must match exactly.
    let b = layout("cache me", &TextOptions { width: Some(100.0), ..Default::default() });
    assert!(!Arc::ptr_eq(&a, &b));
    assert_eq!(a.glyphs.len(), b.glyphs.len());
    for (x, y) in a.glyphs.iter().zip(&b.glyphs) {
        assert_eq!(x.path, y.path);
    }
}
