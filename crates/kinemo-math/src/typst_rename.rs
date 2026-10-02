//! Renames in mitex's typst output: mitex 0.2.4 targets an older typst, and a
//! few symbol names changed since (`sect` → `inter`, `diff` → `partial`,
//! `plus.circle` → `plus.o`, ...). Only identifiers in math are renamed; text
//! inside markup blocks (`#textmath[...]`) and strings is left alone. Literal
//! delimiter characters are escaped (see [`DELIMITER_CHARS`]).

/// Old mitex alias → typst 0.15 name. Matched against whole dotted identifiers.
const RENAMES: &[(&str, &str)] = &[
    ("sect", "inter"),
    ("sect.big", "inter.big"),
    ("sect.double", "inter.double"),
    ("sect.sq", "inter.sq"),
    ("diff", "partial"),
    ("planck.reduce", "planck"),
    ("angle.l", "chevron.l"),
    ("angle.r", "chevron.r"),
    ("bracket.l.double", "bracket.l.stroked"),
    ("bracket.r.double", "bracket.r.stroked"),
    ("dot.circle", "dot.o"),
    ("dot.circle.big", "dot.o.big"),
    ("plus.circle", "plus.o"),
    ("plus.circle.big", "plus.o.big"),
    ("minus.circle", "minus.o"),
    ("times.circle", "times.o"),
    ("times.circle.big", "times.o.big"),
    ("ast.circle", "ast.op.o"),
    ("circle.nested", "compose.o"),
    ("dash.circle", "dash.o"),
    ("arrow.l.dash", "arrow.l.dashed"),
    ("arrow.r.dash", "arrow.r.dashed"),
    ("ohm.inv", "Omega.inv"),
    // `set` is a typst keyword and cannot be defined in the prelude.
    ("set", "mitexset"),
];

/// Literal delimiter characters mitex emits that typst's math parser would try
/// to pair (breaking marker calls like `colortext(1, ⌊)`). They are written as
/// unicode escapes, which typst does not pair but still treats as delimiters.
const DELIMITER_CHARS: &[char] = &[
    '⌊', '⌋', '⌈', '⌉', '⦃', '⦄', '⟮', '⟯', '⌜', '⌝', '⌞', '⌟', '⟨', '⟩', '⟦', '⟧', '⦇', '⦈', '⦉', '⦊',
    '⟬', '⟭', '⦅', '⦆', '⦗', '⦘', '〈', '〉', '❲', '❳', '⟅', '⟆',
];

fn renamed(identifier: &str) -> &str {
    RENAMES.iter().find(|(old, _)| *old == identifier).map(|(_, new)| *new).unwrap_or(identifier)
}

/// Apply [`RENAMES`] to the identifiers of typst math markup `math`.
pub(crate) fn rename_identifiers(math: &str) -> String {
    let chars: Vec<char> = math.chars().collect();
    let mut out = String::with_capacity(math.len());
    let mut markup_depth = 0usize;
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '\\' {
            out.push(c);
            if let Some(&next) = chars.get(i + 1) {
                out.push(next);
            }
            i += 2;
            continue;
        }
        if c == '"' {
            let end = (i + 1..chars.len()).find(|&j| chars[j] == '"' && chars[j - 1] != '\\').unwrap_or(chars.len() - 1);
            out.extend(&chars[i..=end]);
            i = end + 1;
            continue;
        }
        match c {
            '[' => markup_depth += 1,
            ']' => markup_depth = markup_depth.saturating_sub(1),
            _ => {}
        }
        if markup_depth == 0 && DELIMITER_CHARS.contains(&c) {
            out.push_str(&format!("\\u{{{:X}}}", c as u32));
            i += 1;
            continue;
        }
        let starts_identifier = c.is_ascii_alphabetic() && (i == 0 || !is_identifier_char(chars[i - 1]));
        if markup_depth == 0 && starts_identifier {
            let mut end = i;
            while end < chars.len() && (is_identifier_char(chars[end]) || chars[end] == '.') {
                end += 1;
            }
            while end > i && chars[end - 1] == '.' {
                end -= 1;
            }
            let identifier: String = chars[i..end].iter().collect();
            out.push_str(renamed(&identifier));
            i = end;
            continue;
        }
        out.push(c);
        i += 1;
    }
    out
}

fn is_identifier_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '-' || c == '_'
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renames_whole_identifiers_only() {
        assert_eq!(rename_identifiers("A sect B"), "A inter B");
        assert_eq!(rename_identifiers("sect.big _(i)"), "inter.big _(i)");
        assert_eq!(rename_identifiers("frac(diff f, diff x)"), "frac(partial f, partial x)");
        assert_eq!(rename_identifiers("angle.l x angle.r"), "chevron.l x chevron.r");
        assert_eq!(rename_identifiers("angle x"), "angle x");
        assert_eq!(rename_identifiers("sects"), "sects");
        assert_eq!(rename_identifiers("#textmath[sect diff];"), "#textmath[sect diff];");
        assert_eq!(rename_identifiers("\\[ diff \\]"), "\\[ partial \\]");
        assert_eq!(rename_identifiers("f(⌊ x ⌋)"), "f(\\u{230A} x \\u{230B})");
    }
}
