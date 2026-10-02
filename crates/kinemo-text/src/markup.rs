//! Minimal inline markup: `**bold**`, `*italic*`, `` `code` `` (mono).
//!
//! `$...$` math is kept as literal text for now. Backslash escapes `\*`, `` \` ``,
//! `\$` and `\\` produce the literal character. A marker without a matching
//! closer is kept literally (so `2 * 3` stays as is).

use crate::types::{FontStyle, TextOptions};

/// Parse `text` into plain chars, each with its font style.
pub(crate) fn parse(text: &str, opts: &TextOptions) -> Vec<(char, FontStyle)> {
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
            return true;
        }
        j += 1;
    }
    false
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
        assert_eq!(plain("`a*b*c`"), "a*b*c");
    }

    #[test]
    fn styles() {
        let p = parse("a**b***c*`d`", &TextOptions::default());
        let st: Vec<FontStyle> = p.iter().map(|x| x.1).collect();
        assert_eq!(st, vec![FontStyle::Regular, FontStyle::Bold, FontStyle::Italic, FontStyle::Mono]);
    }
}
