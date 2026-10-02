//! Normalized TeX of AST items, used to match subexpressions by syntax tree:
//! redundant braces around single items are dropped (`c^2` ≡ `c^{2}`), script
//! arguments are always braced and written `_` before `^`, spacing is dropped,
//! and whitespace only separates a control word from a following letter.

use crate::latex_parser::Ast;

/// Where an item appears; script bases keep braces around multi-item groups.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Context {
    List,
    Base,
}

/// Normalized TeX of a math list.
pub(crate) fn list_tex(items: &[Ast]) -> String {
    join(items.iter().map(|item| item_tex(item, Context::List)))
}

/// Normalized TeX of one item (as it appears inside a list).
pub(crate) fn single_tex(item: &Ast) -> String {
    item_tex(item, Context::List)
}

/// Number of items that contribute to normalized TeX.
fn meaningful_len(items: &[Ast]) -> usize {
    items.iter().filter(|i| !matches!(i, Ast::Raw { semantic: false, .. })).count()
}

fn braced_list(items: &[Ast], braces_when_many: bool) -> String {
    let inner = list_tex(items);
    if braces_when_many && meaningful_len(items) > 1 {
        format!("{{{inner}}}")
    } else {
        inner
    }
}

fn item_tex(item: &Ast, context: Context) -> String {
    match item {
        Ast::Raw { tex, semantic } => {
            if *semantic {
                tex.clone()
            } else {
                String::new()
            }
        }
        Ast::Atom(tex) => tex.clone(),
        Ast::Group(items) => braced_list(items, true),
        Ast::Id { body, .. } => braced_list(body, context == Context::Base),
        Ast::Command { name, raw_args, args } => {
            let mut parts = vec![format!("\\{name}"), raw_args.clone()];
            parts.extend(args.iter().map(|a| format!("{{{}}}", list_tex(a))));
            join(parts)
        }
        Ast::Script { base, primes, limits, sub, sup } => {
            let mut parts = vec![base.as_deref().map(|b| item_tex(b, Context::Base)).unwrap_or_default()];
            parts.push("'".repeat(*primes));
            parts.extend(limits.clone());
            parts.extend(sub.as_deref().map(|s| format!("_{{{}}}", list_tex(s))));
            parts.extend(sup.as_deref().map(|s| format!("^{{{}}}", list_tex(s))));
            join(parts)
        }
        Ast::LeftRight { left, right, body } => {
            join([format!("\\left{left}"), list_tex(body), format!("\\right{right}")])
        }
        Ast::Environment { name, args, body } => {
            join([format!("\\begin{{{name}}}{args}"), list_tex(body), format!("\\end{{{name}}}")])
        }
    }
}

/// True if `s` ends with a control word (`\alpha`), which would swallow a following letter.
fn ends_with_control_word(s: &str) -> bool {
    let trimmed = s.trim_end_matches(|c: char| c.is_ascii_alphabetic());
    trimmed.len() < s.len() && trimmed.ends_with('\\') && !trimmed.ends_with("\\\\")
}

/// Concatenate pieces, separating a control word from a following letter.
fn join(pieces: impl IntoIterator<Item = String>) -> String {
    let mut out = String::new();
    for piece in pieces {
        if piece.is_empty() {
            continue;
        }
        if ends_with_control_word(&out) && piece.starts_with(|c: char| c.is_ascii_alphabetic()) {
            out.push(' ');
        }
        out.push_str(&piece);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::latex_parser::parse;

    fn norm(s: &str) -> String {
        list_tex(&parse(s).unwrap())
    }

    #[test]
    fn redundant_braces_and_spaces() {
        assert_eq!(norm("c^2"), "c^{2}");
        assert_eq!(norm("c^{2}"), "c^{2}");
        assert_eq!(norm("{c}^{{2}}"), "c^{2}");
        assert_eq!(norm("a ^ 2  +  b"), "a^{2}+b");
        assert_eq!(norm(r"\alpha x"), r"\alpha x");
        assert_eq!(norm(r"\alpha+x"), r"\alpha+x");
        assert_eq!(norm(r"x^2_1"), "x_{1}^{2}");
        assert_eq!(norm(r"{a+b}^2"), "{a+b}^{2}");
        assert_eq!(norm(r"\frac12"), r"\frac{1}{2}");
        assert_eq!(norm(r"\int_0^1 x\,dx"), r"\int_{0}^{1}xdx");
        assert_eq!(norm(r"\id{lhs}{a^2 + b^2} = c^2"), "a^{2}+b^{2}=c^{2}");
        assert_eq!(norm(r"\left( x \right)"), r"\left(x\right)");
    }
}
