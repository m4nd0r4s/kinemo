//! Monospace code layout: tokens -> positioned glyph outlines.
//!
//! Each source line is laid out on its own with kinemo-text (mono font, no
//! markup), so per-line layouts are cached and shared between versions of a
//! snippet. Lines are left-aligned; tabs expand to `tab_width` columns; the
//! whole block (gutter included) is centered at the origin, y-up.

use kinemo_text::{Align, TextOptions};
use kurbo::{Affine, BezPath, Rect, Vec2};

use crate::languages::Language;
use crate::tokens::{tokenize_language, Token};
use crate::CodeError;

#[derive(Clone, Debug, PartialEq)]
pub struct CodeOptions {
    /// Font size (em height) in scene units.
    pub size: f64,
    /// Draw a right-aligned line-number gutter left of the code.
    pub line_numbers: bool,
    /// Line height as a multiple of `size`.
    pub line_height: f64,
    /// Columns per tab stop.
    pub tab_width: usize,
}

impl Default for CodeOptions {
    fn default() -> Self {
        CodeOptions {
            size: 0.32,
            line_numbers: false,
            line_height: 1.35,
            tab_width: 4,
        }
    }
}

#[derive(Clone, Debug)]
pub struct CodeGlyph {
    /// Outline in scene units, y-up, positioned in the block.
    pub path: BezPath,
    /// Index into `CodeLayout::tokens`.
    pub token: usize,
    pub line: usize,
    /// Char index into the original source (before tab expansion).
    pub char_index: usize,
}

#[derive(Clone, Debug)]
pub struct CodeLayout {
    /// Visible glyphs in source order (whitespace has no glyph).
    pub glyphs: Vec<CodeGlyph>,
    /// Logical box of the whole block (gutter included), centered at (0,0).
    pub bbox: Rect,
    /// Logical rect of each line's code (x from the code column start to the
    /// line end; an empty line has zero width). Index = line number.
    pub line_rects: Vec<Rect>,
    /// Gutter digit outlines per line; empty vectors when `line_numbers` is off.
    pub line_numbers: Vec<Vec<BezPath>>,
    /// Tokens the glyphs refer to (same as `tokenize`).
    pub tokens: Vec<Token>,
    /// Advance width of one monospace column, in scene units.
    pub column_width: f64,
}

fn text_options(options: &CodeOptions) -> TextOptions {
    TextOptions {
        size: options.size,
        width: None,
        align: Align::Left,
        line_height: options.line_height,
        tabular_nums: true,
        markup: false,
        mono: true,
    }
}

/// Monospace column width: advance of '0' in the mono font.
fn column_width(text_options: &TextOptions) -> f64 {
    let probe = kinemo_text::layout("0", text_options);
    probe
        .glyphs
        .first()
        .map(|glyph| glyph.advance_rect.width())
        .unwrap_or(text_options.size * 0.6)
}

/// One source line with tabs expanded; `source_char[i]` maps expanded char `i`
/// back to the original source char index.
struct ExpandedLine {
    text: String,
    source_char: Vec<usize>,
}

fn expand_lines(source: &str, tab_width: usize) -> Vec<ExpandedLine> {
    let tab_width = tab_width.max(1);
    let mut lines = Vec::new();
    let mut current = ExpandedLine {
        text: String::new(),
        source_char: Vec::new(),
    };
    for (char_index, character) in source.chars().enumerate() {
        match character {
            '\n' => lines.push(std::mem::replace(
                &mut current,
                ExpandedLine {
                    text: String::new(),
                    source_char: Vec::new(),
                },
            )),
            '\t' => {
                let spaces = tab_width - current.source_char.len() % tab_width;
                for _ in 0..spaces {
                    current.text.push(' ');
                    current.source_char.push(char_index);
                }
            }
            '\r' => {}
            _ => {
                current.text.push(character);
                current.source_char.push(char_index);
            }
        }
    }
    // A trailing newline ends the last line rather than starting an empty one.
    if !current.source_char.is_empty() || lines.is_empty() || !source.ends_with('\n') {
        lines.push(current);
    }
    lines
}

pub(crate) fn compute_layout(
    source: &str,
    language: Language,
    options: &CodeOptions,
) -> Result<CodeLayout, CodeError> {
    let tokens = tokenize_language(source, language)?;
    let char_count = source.chars().count();
    let mut token_of_char = vec![usize::MAX; char_count];
    for (token_index, token) in tokens.iter().enumerate() {
        token_of_char[token.start_char..token.end_char].fill(token_index);
    }

    let text_options = text_options(options);
    let column = column_width(&text_options);
    let line_height = options.size * options.line_height;
    let lines = expand_lines(source, options.tab_width);
    let line_count = lines.len();

    let digit_count = line_count.to_string().len();
    let gutter_width = if options.line_numbers {
        (digit_count as f64 + 2.0) * column
    } else {
        0.0
    };
    let max_columns = lines
        .iter()
        .map(|line| line.source_char.len())
        .max()
        .unwrap_or(0);
    let total_width = gutter_width + max_columns as f64 * column;
    let total_height = line_count as f64 * line_height;
    // Block built with its top-left corner at (left, top).
    let (left, top) = (-total_width / 2.0, total_height / 2.0);
    let code_left = left + gutter_width;

    let mut glyphs = Vec::new();
    let mut line_rects = Vec::with_capacity(line_count);
    let mut line_numbers = Vec::with_capacity(line_count);
    for (line_index, line) in lines.iter().enumerate() {
        let line_top = top - line_index as f64 * line_height;
        let mut line_width = 0.0;
        if !line.text.trim().is_empty() {
            let line_layout = kinemo_text::layout(&line.text, &text_options);
            line_width = line_layout.bbox.width();
            let offset = Vec2::new(
                code_left - line_layout.bbox.x0,
                line_top - line_layout.bbox.y1,
            );
            for glyph in &line_layout.glyphs {
                let char_index = line.source_char[glyph.char_index];
                let token = token_of_char[char_index];
                if token == usize::MAX {
                    continue;
                }
                glyphs.push(CodeGlyph {
                    path: Affine::translate(offset) * glyph.path.clone(),
                    token,
                    line: line_index,
                    char_index,
                });
            }
        }
        line_rects.push(Rect::new(
            code_left,
            line_top - line_height,
            code_left + line_width,
            line_top,
        ));

        let mut number_paths = Vec::new();
        if options.line_numbers {
            let label = (line_index + 1).to_string();
            let number_layout = kinemo_text::layout(&label, &text_options);
            // Right-aligned, one column of padding before the code.
            let right = code_left - column;
            let offset = Vec2::new(
                right - number_layout.bbox.x1,
                line_top - number_layout.bbox.y1,
            );
            number_paths.extend(
                number_layout
                    .glyphs
                    .iter()
                    .map(|glyph| Affine::translate(offset) * glyph.path.clone()),
            );
        }
        line_numbers.push(number_paths);
    }

    Ok(CodeLayout {
        glyphs,
        bbox: Rect::new(left, -top, -left, top),
        line_rects,
        line_numbers,
        tokens,
        column_width: column,
    })
}
