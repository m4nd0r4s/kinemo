//! Public data types: options and layout results.

use kurbo::{BezPath, Rect};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum FontStyle {
    Regular,
    Bold,
    Italic,
    Mono,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Align {
    Left,
    Center,
    Right,
}

#[derive(Clone, Debug, PartialEq)]
pub struct TextOptions {
    /// Font size = em height, in scene units.
    pub size: f64,
    /// Wrap width in scene units; `None` = single line (explicit '\n' still breaks).
    pub width: Option<f64>,
    /// Line alignment within the block.
    pub align: Align,
    /// Line height as a multiple of `size`.
    pub line_height: f64,
    /// Digits use tabular widths (OpenType `tnum`).
    pub tabular_nums: bool,
    /// Parse `**bold**`, `*italic*`, `` `code` ``. `$...$` is kept literal.
    pub markup: bool,
    /// Whole text in the mono font.
    pub mono: bool,
}

impl Default for TextOptions {
    fn default() -> Self {
        TextOptions {
            size: 0.5,
            width: None,
            align: Align::Left,
            line_height: 1.25,
            tabular_nums: true,
            markup: true,
            mono: false,
        }
    }
}

#[derive(Clone, Debug)]
pub struct Glyph {
    /// Outline in scene units, y-up, positioned in the block.
    pub path: BezPath,
    /// Char index into `TextLayout::plain` of the cluster start.
    pub char_index: usize,
    pub line: usize,
    /// Index of the whitespace-separated word (into `TextLayout::words`).
    pub word: usize,
    /// Advance box: x from pen to pen+advance, y from descender to ascender (y-up).
    pub advance_rect: Rect,
    pub style: FontStyle,
}

#[derive(Clone, Debug)]
pub struct TextLayout {
    /// Text with markup stripped (contains explicit '\n').
    pub plain: String,
    /// Visible glyphs; whitespace glyphs are omitted.
    pub glyphs: Vec<Glyph>,
    /// Logical box, centered at (0,0), y-up.
    pub bbox: Rect,
    /// Logical rect per line.
    pub lines: Vec<Rect>,
    /// Char ranges `[start, end)` of whitespace-separated words in `plain`.
    pub words: Vec<(usize, usize)>,
}
