use std::time::Instant;

use kinemo_code::{layout_code, tokenize, CodeOptions, Palette, TokenKind};
use kurbo::Shape;

const SOURCE: &str = "def area(r):\n\treturn 3.14 * r * r\n\nprint(area(2))\n";

#[test]
fn line_count_and_rects() {
    let layout = layout_code(SOURCE, "python", &CodeOptions::default()).unwrap();
    assert_eq!(layout.line_rects.len(), 4);
    assert_eq!(layout.line_numbers.len(), 4);
    assert!(layout.line_numbers.iter().all(Vec::is_empty));
    // Lines go downwards (y-up), left-aligned to the same column.
    for pair in layout.line_rects.windows(2) {
        assert!(pair[1].y1 <= pair[0].y0 + 1e-9);
        assert!((pair[1].x0 - pair[0].x0).abs() < 1e-9);
    }
    assert_eq!(layout.line_rects[2].width(), 0.0);
    // Centered block.
    let bbox = layout.bbox;
    assert!((bbox.x0 + bbox.x1).abs() < 1e-9 && (bbox.y0 + bbox.y1).abs() < 1e-9);
    let expected_height = 4.0 * 0.32 * 1.35;
    assert!((bbox.height() - expected_height).abs() < 1e-9);
}

#[test]
fn every_visible_char_has_a_glyph_mapped_to_its_token() {
    let layout = layout_code(SOURCE, "python", &CodeOptions::default()).unwrap();
    let tokens = tokenize(SOURCE, "python").unwrap();
    assert_eq!(layout.tokens, tokens);
    let visible: Vec<usize> = SOURCE
        .chars()
        .enumerate()
        .filter(|(_, c)| !c.is_whitespace())
        .map(|(index, _)| index)
        .collect();
    let glyph_chars: Vec<usize> = layout.glyphs.iter().map(|glyph| glyph.char_index).collect();
    assert_eq!(glyph_chars, visible);
    for glyph in &layout.glyphs {
        let token = &tokens[glyph.token];
        assert!(token.start_char <= glyph.char_index && glyph.char_index < token.end_char);
        assert_eq!(token.line, glyph.line);
        let bounds = glyph.path.bounding_box();
        assert!(
            layout.bbox.inflate(1e-6, 1e-6).contains_rect(bounds),
            "{bounds:?} outside {:?}",
            layout.bbox
        );
    }
}

#[test]
fn tabs_expand_to_tab_stops() {
    let options = CodeOptions::default();
    let spaces = layout_code("a\n    b", "text", &options).unwrap();
    let tab = layout_code("a\n\tb", "text", &options).unwrap();
    let x_of =
        |layout: &kinemo_code::CodeLayout| layout.glyphs[1].path.bounding_box().x0 - layout.bbox.x0;
    assert!((x_of(&spaces) - x_of(&tab)).abs() < 1e-9);
}

#[test]
fn line_number_gutter() {
    let source = (1..=12)
        .map(|i| format!("x{i} = {i}"))
        .collect::<Vec<_>>()
        .join("\n");
    let plain = layout_code(&source, "python", &CodeOptions::default()).unwrap();
    let options = CodeOptions {
        line_numbers: true,
        ..CodeOptions::default()
    };
    let numbered = layout_code(&source, "python", &options).unwrap();
    assert_eq!(numbered.line_numbers.len(), 12);
    assert_eq!(numbered.line_numbers[0].len(), 1);
    assert_eq!(numbered.line_numbers[11].len(), 2);
    assert!(numbered.bbox.width() > plain.bbox.width());
    // Numbers sit left of the code column.
    let code_left = numbered.line_rects[0].x0;
    for paths in &numbered.line_numbers {
        for path in paths {
            assert!(path.bounding_box().x1 < code_left);
        }
    }
}

#[test]
fn layout_is_cached_and_deterministic() {
    let options = CodeOptions::default();
    let first = layout_code(SOURCE, "python", &options).unwrap();
    let second = layout_code(SOURCE, "py", &options).unwrap();
    assert!(std::sync::Arc::ptr_eq(&first, &second));
    let other_options = CodeOptions {
        size: 0.5,
        ..options
    };
    let bigger = layout_code(SOURCE, "python", &other_options).unwrap();
    assert!(bigger.bbox.width() > first.bbox.width());
}

#[test]
fn palette_colors() {
    let dark = Palette::dark();
    let light = Palette::light();
    assert_ne!(
        dark.color(TokenKind::Keyword),
        light.color(TokenKind::Keyword)
    );
    assert_ne!(
        dark.color(TokenKind::Keyword),
        dark.color(TokenKind::String)
    );
    assert!(dark
        .color(TokenKind::Comment)
        .iter()
        .all(|c| (0.0..=1.0).contains(c)));
}

#[test]
fn fifty_line_file_is_fast() {
    let source: String = (0..50)
        .map(|i| {
            format!(
                "def function_{i}(value, *args):\n    return value * {i} + len(args)  # line {i}\n"
            )
        })
        .take(25)
        .collect();
    assert_eq!(source.lines().count(), 50);
    let options = CodeOptions {
        line_numbers: true,
        ..CodeOptions::default()
    };
    let start = Instant::now();
    let layout = layout_code(&source, "python", &options).unwrap();
    let elapsed = start.elapsed();
    eprintln!(
        "50-line python layout (cold): {elapsed:?}, {} glyphs",
        layout.glyphs.len()
    );
    assert_eq!(layout.line_rects.len(), 50);
    assert!(elapsed.as_millis() < 500, "took {elapsed:?}");
    let start = Instant::now();
    layout_code(&source, "python", &options).unwrap();
    assert!(start.elapsed().as_millis() < 5);
}
