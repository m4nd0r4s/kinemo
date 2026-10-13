//! Minimal inline markup: `**bold**`, `*italic*`, `` `code` `` (mono), `$math$`.
//!
//! A `$...$` span becomes one [`INLINE_CHAR`] with the `Inline` style when the caller gives
//! the boxes of the spans (`TextOptions::inline`); otherwise it stays literal text. Backslash
//! escapes `\*`, `` \` ``, `\$` and `\\` produce the literal character. A marker without a
//! matching closer is kept literally (so `2 * 3` and `$5` stay as they are).

use crate::types::{FontStyle, TextOptions};

/// The char that stands for a `$math$` span in `TextLayout::plain`.
pub const INLINE_CHAR: char = '\u{FFFC}';

/// Parse `text` into plain chars, each with its font style.
pub(crate) fn parse(text: &str, opts: &TextOptions) -> Vec<(char, FontStyle)> {
    scan(text, opts, !opts.inline.is_empty(), &mut Vec::new())
}

/// The TeX of each `$...$` span of `text`, in order: what the caller lays out and gives back
/// as `TextOptions::inline`. Empty when markup is off.
pub fn math_spans(text: &str, opts: &TextOptions) -> Vec<String> {
    let mut spans = Vec::new();
    scan(text, opts, true, &mut spans);
    spans
}

fn scan(text: &str, opts: &TextOptions, inline: bool, spans: &mut Vec<String>) -> Vec<(char, FontStyle)> {
    let chars: Vec<char> = text.chars().collect();
    let style_of = |bold: bool, italic: bool, code: bool| {
        if opts.mono || code {
            FontStyle::Mono
        } else if bold {
            FontStyle::Bold
        } else if italic {
            FontStyle::Italic
        } else {
            FontStyle::Regular
        }
    };
    if !opts.markup {
        let st = style_of(false, false, false);
        return chars.into_iter().map(|c| (c, st)).collect();
    }

    let (mut bold, mut italic, mut code) = (false, false, false);
    let mut out = Vec::with_capacity(chars.len());
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '\\' {
            if let Some(&n) = chars.get(i + 1) {
                if matches!(n, '*' | '`' | '$' | '\\') {
                    out.push((n, style_of(bold, italic, code)));
                    i += 2;
                    continue;
                }
            }
        } else if c == '$' && inline && !code {
            if let Some(end) = math_closer(&chars, i) {
                spans.push(chars[i + 1..end].iter().collect());
                out.push((INLINE_CHAR, FontStyle::Inline));
                i = end + 1;
                continue;
            }
        } else if c == '`' {
            if code || has_closer(&chars, i + 1, &['`']) {
                code = !code;
                i += 1;
                continue;
            }
        } else if c == '*' && !code {
            if chars.get(i + 1) == Some(&'*') {
                if bold || has_closer(&chars, i + 2, &['*', '*']) {
                    bold = !bold;
                    i += 2;
                    continue;
                }
            } else if italic || has_closer(&chars, i + 1, &['*']) {
                italic = !italic;
                i += 1;
                continue;
            }
        }
        out.push((c, style_of(bold, italic, code)));
        i += 1;
    }
    out
}

/// Is there an unescaped `marker` at or after `from`? A single `*` marker does
/// not match the start of a `**`.
fn has_closer(chars: &[char], from: usize, marker: &[char]) -> bool {
    find_closer(chars, from, marker).is_some()
}

/// The closing `$` of a math span opened at `open`, as Pandoc reads them: the opening `$`
/// has a non-space right after it, the closing one a non-space right before it and no digit
/// right after it. So `$x^2$` is math, `costs $5 and $10` is not.
fn math_closer(chars: &[char], open: usize) -> Option<usize> {
    if chars.get(open + 1).is_none_or(|c| c.is_whitespace() || *c == '$') {
        return None;
    }
    let mut j = open + 1;
    while j < chars.len() {
        if chars[j] == '\\' && j + 1 < chars.len() {
            j += 2;
            continue;
        }
        if chars[j] == '$' && !chars[j - 1].is_whitespace() && !chars.get(j + 1).is_some_and(|c| c.is_ascii_digit()) {
            return Some(j);
        }
        j += 1;
    }
    None
}

/// Index of the first unescaped `marker` at or after `from` (see [`has_closer`]).
fn find_closer(chars: &[char], from: usize, marker: &[char]) -> Option<usize> {
    let mut j = from;
    while j < chars.len() {
        if chars[j] == '\\' && j + 1 < chars.len() {
            j += 2;
            continue;
        }
        if chars[j..].starts_with(marker) {
            if marker == ['*'] && chars.get(j + 1) == Some(&'*') {
                j += 2;
                continue;
            }
            return Some(j);
        }
        j += 1;
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn plain(s: &str) -> String {
        parse(s, &TextOptions::default()).into_iter().map(|(c, _)| c).collect()
    }

    #[test]
    fn strips_and_escapes() {
        assert_eq!(plain("a **b** *c* `d`"), "a b c d");
        assert_eq!(plain(r"\*x\* \` \$ \\"), r"*x* ` $ \");
        assert_eq!(plain("2 * 3"), "2 * 3");
        assert_eq!(plain("$x^2$"), "$x^2$");
        assert_eq!(plain("costs $5"), "costs $5");
        assert_eq!(plain("`a*b*c`"), "a*b*c");
    }

    #[test]
    fn math_spans_become_one_inline_char_when_boxes_are_given() {
        let opts = TextOptions { inline: vec![crate::types::InlineBox { width: 1.0, ascent: 0.4, descent: 0.1 }; 2], ..TextOptions::default() };
        assert_eq!(math_spans(r"slope $f'(x)$ and `$no$` then $x^2$ and \$5", &opts), vec!["f'(x)".to_string(), "x^2".to_string()]);
        let parsed = parse(r"a $x$ b \$5", &opts);
        let plain: String = parsed.iter().map(|(c, _)| *c).collect();
        assert_eq!(plain, "a \u{FFFC} b $5");
        assert_eq!(parsed[2].1, FontStyle::Inline);
        assert_eq!(math_spans("$$ and $5", &opts), Vec::<String>::new());
        assert_eq!(math_spans("costs $5 and $10 today", &opts), Vec::<String>::new());
        assert_eq!(math_spans("between $a$ and $b$", &opts), vec!["a".to_string(), "b".to_string()]);
    }

    #[test]
    fn styles() {
        let p = parse("a**b***c*`d`", &TextOptions::default());
        let st: Vec<FontStyle> = p.iter().map(|x| x.1).collect();
        assert_eq!(st, vec![FontStyle::Regular, FontStyle::Bold, FontStyle::Italic, FontStyle::Mono]);
    }
}
