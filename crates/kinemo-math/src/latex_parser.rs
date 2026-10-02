//! A small LaTeX math parser. It only recovers the structure kinemo needs for
//! the part tree (groups, scripts, commands and their arguments, `\left...\right`,
//! environments, `\id{name}{...}`); converting to typst is left to mitex.
//! Command arities come from the mitex specification, so anything this parser
//! accepts is also known to mitex.

use std::ops::{Deref, DerefMut};

pub(crate) use crate::ast::Ast;
use crate::ast::{is_x_arrow, INVISIBLE_COMMANDS, INVISIBLE_COMMANDS_WITH_ARGUMENT, MATH_ARGUMENT_COMMANDS};
use crate::command_spec::{command_arity, environment_arity, Arity};
use crate::error::MathError;
use crate::latex_scanner::{syntax, Scanner};

/// Parse a math-mode LaTeX string.
pub(crate) fn parse(tex: &str) -> Result<Vec<Ast>, MathError> {
    let mut parser = Parser { scanner: Scanner::new(tex) };
    let list = parser.list()?;
    parser.skip_whitespace();
    match parser.peek() {
        None => Ok(list),
        Some('}') => Err(MathError::Syntax("unmatched `}`".into())),
        Some(_) => {
            let word = parser.peek_control_word().unwrap_or_default();
            Err(MathError::Syntax(format!("unexpected `\\{word}`")))
        }
    }
}

struct Parser {
    scanner: Scanner,
}

impl Deref for Parser {
    type Target = Scanner;
    fn deref(&self) -> &Scanner {
        &self.scanner
    }
}

impl DerefMut for Parser {
    fn deref_mut(&mut self) -> &mut Scanner {
        &mut self.scanner
    }
}

impl Parser {
    /// One math argument: `{list}` or a single item without scripts.
    fn term(&mut self) -> Result<Vec<Ast>, MathError> {
        self.skip_whitespace();
        match self.peek() {
            None => Err(syntax("missing argument")),
            Some('{') => {
                self.pos += 1;
                let list = self.list()?;
                self.expect_close_brace()?;
                Ok(list)
            }
            Some('}') => Err(syntax("missing argument before `}`")),
            Some(_) => Ok(self.primary(true)?.into_iter().collect()),
        }
    }

    fn expect_close_brace(&mut self) -> Result<(), MathError> {
        self.skip_whitespace();
        if self.bump() == Some('}') {
            Ok(())
        } else {
            Err(syntax("missing `}`"))
        }
    }

    /// A math list, up to `}`, `\right`, `\end` or the end of input (not consumed).
    fn list(&mut self) -> Result<Vec<Ast>, MathError> {
        let mut items = Vec::new();
        loop {
            self.skip_whitespace();
            match self.peek() {
                None | Some('}') => break,
                Some('\\') if matches!(self.peek_control_word().as_deref(), Some("right" | "end")) => break,
                _ => {}
            }
            let base = match self.peek() {
                Some('^' | '_' | '\'') => None,
                _ => self.primary(false)?,
            };
            items.push(self.postfix(base)?);
        }
        Ok(items)
    }

    /// Attach primes, `\limits` and scripts that follow `base`.
    fn postfix(&mut self, base: Option<Ast>) -> Result<Ast, MathError> {
        let (mut primes, mut limits, mut sub, mut sup) = (0, None, None, None);
        loop {
            self.skip_whitespace();
            match self.peek() {
                Some('\'') => {
                    self.pos += 1;
                    primes += 1;
                }
                Some('^') => {
                    self.pos += 1;
                    if sup.is_some() {
                        return Err(syntax("double superscript"));
                    }
                    sup = Some(self.term()?);
                }
                Some('_') => {
                    self.pos += 1;
                    if sub.is_some() {
                        return Err(syntax("double subscript"));
                    }
                    sub = Some(self.term()?);
                }
                Some('\\') if matches!(self.peek_control_word().as_deref(), Some("limits" | "nolimits")) => {
                    let word = self.peek_control_word().unwrap_or_default();
                    self.pos += 1 + word.len();
                    limits = Some(format!("\\{word}"));
                }
                _ => break,
            }
        }
        let scripted = primes > 0 || limits.is_some() || sub.is_some() || sup.is_some();
        match base {
            Some(base) if !scripted => Ok(base),
            base if scripted => Ok(Ast::Script { base: base.map(Box::new), primes, limits, sub, sup }),
            _ => Err(syntax("empty item")),
        }
    }

    /// One item without scripts. `in_term`: a lone digit is one item (`x^23`).
    fn primary(&mut self, in_term: bool) -> Result<Option<Ast>, MathError> {
        self.skip_whitespace();
        let Some(c) = self.peek() else { return Ok(None) };
        match c {
            '{' => {
                self.pos += 1;
                let list = self.list()?;
                self.expect_close_brace()?;
                if list.is_empty() {
                    Ok(Some(Ast::Raw { tex: "{}".into(), semantic: false }))
                } else {
                    Ok(Some(Ast::Group(list)))
                }
            }
            '}' => Ok(None),
            '^' | '_' => Err(syntax(format!("misplaced `{c}`"))),
            '$' => Err(syntax("`$` inside math")),
            '&' => {
                self.pos += 1;
                Ok(Some(Ast::Raw { tex: "&".into(), semantic: true }))
            }
            '~' => {
                self.pos += 1;
                Ok(Some(Ast::Raw { tex: "~".into(), semantic: false }))
            }
            '0'..='9' => Ok(Some(Ast::Atom(self.number(in_term)))),
            '\\' => {
                self.pos += 1;
                self.command()
            }
            _ => {
                self.pos += 1;
                Ok(Some(Ast::Atom(c.to_string())))
            }
        }
    }

    fn number(&mut self, single_digit: bool) -> String {
        let mut out = String::new();
        while let Some(c) = self.peek() {
            let digit = c.is_ascii_digit();
            let decimal_point = c == '.' && self.peek_at(1).is_some_and(|d| d.is_ascii_digit()) && !out.is_empty();
            if !(digit || decimal_point) || (single_digit && !out.is_empty()) {
                break;
            }
            out.push(c);
            self.pos += 1;
        }
        out
    }

    /// A delimiter after `\left`, `\right`, `\middle`.
    fn delimiter(&mut self) -> Result<String, MathError> {
        self.skip_whitespace();
        match self.bump() {
            None => Err(syntax("missing delimiter")),
            Some('\\') => {
                let name = self.control_sequence()?;
                if name.chars().all(|c| c.is_ascii_alphabetic()) && command_arity(&name).is_none() {
                    return Err(MathError::Unsupported { command: format!("\\{name}") });
                }
                Ok(format!("\\{name}"))
            }
            Some(c) => Ok(c.to_string()),
        }
    }

    /// Item starting with a control sequence (the backslash is consumed).
    fn command(&mut self) -> Result<Option<Ast>, MathError> {
        let name = self.control_sequence()?;
        let raw = |tex: String, semantic: bool| Ok(Some(Ast::Raw { tex, semantic }));
        if !name.chars().next().is_some_and(|c| c.is_ascii_alphabetic()) {
            return match name.as_str() {
                "\\" => {
                    let optional = self.raw_optional()?.unwrap_or_default();
                    raw(format!("\\\\{optional}"), true)
                }
                "," | ";" | ":" | "!" | " " | ">" => raw(format!("\\{name}"), false),
                _ => Ok(Some(Ast::Atom(format!("\\{name}")))),
            };
        }
        match name.as_str() {
            "id" => {
                let raw_name = self.raw_term()?;
                let id_name = raw_name.trim_start_matches('{').trim_end_matches('}').trim().to_owned();
                let body = self.term()?;
                return Ok(Some(Ast::Id { name: id_name, body }));
            }
            "left" => return self.left_right().map(Some),
            "right" => return Err(syntax("`\\right` without `\\left`")),
            "middle" => {
                let delimiter = self.delimiter()?;
                return raw(format!("\\middle{delimiter}"), true);
            }
            "begin" => return self.environment().map(Some),
            "textcolor" => {
                // TeX colors are ignored (kinemo colors parts itself, and
                // `\textcolor` carries the part markers).
                self.raw_term()?;
                let body = self.term()?;
                return Ok(Some(Ast::Group(body)));
            }
            "end" => return Err(syntax("`\\end` without `\\begin`")),
            _ => {}
        }
        let arity = command_arity(&name).ok_or_else(|| MathError::Unsupported { command: format!("\\{name}") })?;
        if INVISIBLE_COMMANDS.contains(&name.as_str()) {
            return raw(format!("\\{name}"), false);
        }
        if INVISIBLE_COMMANDS_WITH_ARGUMENT.contains(&name.as_str()) {
            let argument = self.raw_term()?;
            return raw(format!("\\{name}{argument}"), false);
        }
        match arity {
            Arity::Greedy => return raw(format!("\\{name}"), false),
            Arity::Infix | Arity::Postfix => return raw(format!("\\{name}"), true),
            _ => {}
        }
        if MATH_ARGUMENT_COMMANDS.contains(&name.as_str()) && arity != Arity::None {
            return self.math_command(name, arity).map(Some);
        }
        let args = self.raw_arguments(arity)?;
        Ok(Some(Ast::Atom(format!("\\{name}{args}"))))
    }

    fn math_command(&mut self, name: String, arity: Arity) -> Result<Ast, MathError> {
        let mut raw_args = String::new();
        let count = match arity {
            Arity::Terms(n) => n as usize,
            _ => 1,
        };
        if arity == Arity::OptionalThenTerm {
            raw_args = self.raw_optional()?.unwrap_or_default();
        }
        if is_x_arrow(&name) {
            // `\xrightarrow[below]{above}`: mitex only knows the `{above}` form.
            if let Some(below) = self.raw_optional()? {
                let mut inner = Parser { scanner: Scanner::new(&below[1..below.len() - 1]) };
                let below = inner.list()?;
                let arrow = Ast::Command { name, raw_args, args: vec![self.term()?] };
                return Ok(Ast::Command { name: "underset".into(), raw_args: String::new(), args: vec![below, vec![arrow]] });
            }
        }
        let args = (0..count).map(|_| self.term()).collect::<Result<Vec<_>, _>>()?;
        Ok(Ast::Command { name, raw_args, args })
    }

    fn left_right(&mut self) -> Result<Ast, MathError> {
        let left = self.delimiter()?;
        let body = self.list()?;
        self.skip_whitespace();
        if self.peek_control_word().as_deref() != Some("right") {
            return Err(syntax("`\\left` without `\\right`"));
        }
        self.pos += "\\right".len();
        let right = self.delimiter()?;
        Ok(Ast::LeftRight { left, right, body })
    }

    fn environment(&mut self) -> Result<Ast, MathError> {
        let raw_name = self.raw_term()?;
        let name = raw_name.trim_start_matches('{').trim_end_matches('}').trim().to_owned();
        let arity = environment_arity(&name)
            .ok_or_else(|| MathError::Unsupported { command: format!("\\begin{{{name}}}") })?;
        let args = self.raw_arguments(arity)?;
        let body = self.list()?;
        self.skip_whitespace();
        if self.peek_control_word().as_deref() != Some("end") {
            return Err(syntax(format!("`\\begin{{{name}}}` without `\\end`")));
        }
        self.pos += "\\end".len();
        let end_name = self.raw_term()?;
        if end_name.trim_start_matches('{').trim_end_matches('}').trim() != name {
            return Err(syntax(format!("`\\begin{{{name}}}` closed by `\\end{end_name}`")));
        }
        Ok(Ast::Environment { name, args, body })
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    fn atom(s: &str) -> Ast {
        Ast::Atom(s.into())
    }

    #[test]
    fn scripts_and_groups() {
        let ast = parse("c^2").unwrap();
        assert_eq!(
            ast,
            vec![Ast::Script { base: Some(Box::new(atom("c"))), primes: 0, limits: None, sub: None, sup: Some(vec![atom("2")]) }]
        );
        assert_eq!(parse("x^23").unwrap().len(), 2, "only one digit goes up");
        assert_eq!(parse("3.14x").unwrap(), vec![atom("3.14"), atom("x")]);
        assert!(matches!(&parse("{a+b}^2").unwrap()[0], Ast::Script { base: Some(b), .. } if matches!(**b, Ast::Group(_))));
    }

    #[test]
    fn commands() {
        let ast = parse(r"\frac12").unwrap();
        assert!(matches!(&ast[0], Ast::Command { name, args, .. } if name == "frac" && args.len() == 2));
        let ast = parse(r"\sqrt[3]{x}").unwrap();
        assert!(matches!(&ast[0], Ast::Command { raw_args, .. } if raw_args == "[3]"));
        assert_eq!(parse(r"\text{if  x}").unwrap(), vec![atom(r"\text{if x}")]);
        assert!(matches!(parse(r"\foo"), Err(MathError::Unsupported { command }) if command == r"\foo"));
    }

    #[test]
    fn structure_errors() {
        assert!(matches!(parse(r"\frac{a}{b"), Err(MathError::Syntax(_))));
        assert!(matches!(parse(r"\left( x"), Err(MathError::Syntax(_))));
        assert!(matches!(parse(r"a}"), Err(MathError::Syntax(_))));
        assert!(matches!(parse(r"\begin{pmatrix} a"), Err(MathError::Syntax(_))));
        assert!(parse(r"\left( \frac{a}{b} \right)").is_ok());
        assert!(parse(r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}").is_ok());
        assert!(parse(r"\sum\limits_{i=1}^{n} i").is_ok());
    }
}
