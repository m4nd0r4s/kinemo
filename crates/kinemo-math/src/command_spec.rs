//! Command arities from mitex's default specification.
//!
//! Note: mitex 0.2.4's converter always uses its default specification (the
//! `spec` argument of `convert_math` only reaches its parser), so kinemo cannot
//! add commands or change aliases there. Markers therefore reuse
//! `\textcolor{<id>}{...}` (see `parts.rs`), and typst names that changed
//! since mitex 0.2.4 are renamed in its output (see `typst_rename.rs`).

use mitex::{ArgPattern, ArgShape, CommandSpecItem};
use mitex_spec_gen::DEFAULT_SPEC;

/// How a command consumes the tokens around it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Arity {
    /// No arguments (symbols like `\alpha`).
    None,
    /// `n` mandatory terms (`\frac{a}{b}`).
    Terms(u8),
    /// Optional `[...]` then one term (`\sqrt[3]{x}`).
    OptionalThenTerm,
    /// Only an optional `[...]` (`\midrule[1pt]`).
    Optional,
    /// Swallows the rest of the current group (`\displaystyle`, `\color`).
    Greedy,
    /// Infix operator splitting the current group (`\over`, `\choose`).
    Infix,
    /// Postfix modifier of the previous item (`\limits`).
    Postfix,
}

fn arity_of(pattern: &ArgPattern) -> Arity {
    match pattern {
        ArgPattern::None => Arity::None,
        ArgPattern::FixedLenTerm { len } => Arity::Terms(*len),
        ArgPattern::RangeLenTerm { max, .. } => Arity::Terms(*max),
        ArgPattern::Greedy => Arity::Greedy,
        ArgPattern::Glob { pattern } => match &*pattern.0 {
            "{,b}t" => Arity::OptionalThenTerm,
            "{,b}" => Arity::Optional,
            _ => Arity::Terms(1),
        },
    }
}

/// Arity of command `\name`, or `None` if mitex does not know it.
pub(crate) fn command_arity(name: &str) -> Option<Arity> {
    match DEFAULT_SPEC.get(name)? {
        CommandSpecItem::Cmd(c) => Some(match &c.args {
            ArgShape::Right { pattern } => arity_of(pattern),
            ArgShape::Left1 => Arity::Postfix,
            ArgShape::InfixGreedy => Arity::Infix,
        }),
        CommandSpecItem::Env(_) => None,
    }
}

/// Arity of the arguments after `\begin{name}`, or `None` if unknown.
pub(crate) fn environment_arity(name: &str) -> Option<Arity> {
    match DEFAULT_SPEC.get(name)? {
        CommandSpecItem::Env(e) => Some(arity_of(&e.args)),
        CommandSpecItem::Cmd(_) => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arities() {
        assert_eq!(command_arity("frac"), Some(Arity::Terms(2)));
        assert_eq!(command_arity("sqrt"), Some(Arity::OptionalThenTerm));
        assert_eq!(command_arity("alpha"), Some(Arity::None));
        assert_eq!(command_arity("limits"), Some(Arity::Postfix));
        assert_eq!(command_arity("over"), Some(Arity::Infix));
        assert_eq!(command_arity("notacommand"), None);
        assert_eq!(environment_arity("array"), Some(Arity::Terms(1)));
    }
}
