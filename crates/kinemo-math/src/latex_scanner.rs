//! Character-level scanning of LaTeX source: whitespace and comments, control
//! sequences, and raw (unparsed) arguments.

use crate::command_spec::{command_arity, Arity};
use crate::error::MathError;

/// A cursor over the characters of a LaTeX string.
pub(crate) struct Scanner {
    pub(crate) chars: Vec<char>,
    pub(crate) pos: usize,
}

pub(crate) fn syntax(message: impl Into<String>) -> MathError {
    MathError::Syntax(message.into())
}

impl Scanner {
    pub(crate) fn new(text: &str) -> Self {
        Scanner { chars: text.chars().collect(), pos: 0 }
    }

    pub(crate) fn peek(&self) -> Option<char> {
        self.chars.get(self.pos).copied()
    }

    pub(crate) fn peek_at(&self, offset: usize) -> Option<char> {
        self.chars.get(self.pos + offset).copied()
    }

    pub(crate) fn bump(&mut self) -> Option<char> {
        let c = self.peek()?;
        self.pos += 1;
        Some(c)
    }

    pub(crate) fn skip_whitespace(&mut self) {
        while let Some(c) = self.peek() {
            if c.is_whitespace() {
                self.pos += 1;
            } else if c == '%' {
                while let Some(c) = self.bump() {
                    if c == '\n' {
                        break;
                    }
                }
            } else {
                break;
            }
        }
    }

    /// The control word at the cursor (`\name`), without consuming it.
    pub(crate) fn peek_control_word(&self) -> Option<String> {
        if self.peek() != Some('\\') {
            return None;
        }
        let word: String = self.chars[self.pos + 1..].iter().take_while(|c| c.is_ascii_alphabetic()).collect();
        (!word.is_empty()).then_some(word)
    }

    /// Read a control sequence after its backslash: a word (with a `*` suffix
    /// when the starred command exists) or a single symbol.
    pub(crate) fn control_sequence(&mut self) -> Result<String, MathError> {
        let first = self.bump().ok_or_else(|| syntax("trailing `\\`"))?;
        if !first.is_ascii_alphabetic() {
            return Ok(first.to_string());
        }
        let mut name = first.to_string();
        while let Some(c) = self.peek().filter(char::is_ascii_alphabetic) {
            name.push(c);
            self.pos += 1;
        }
        if self.peek() == Some('*') && command_arity(&format!("{name}*")).is_some() {
            self.pos += 1;
            name.push('*');
        }
        Ok(name)
    }

    /// Raw text of one term: a balanced `{...}`, a control sequence or a char.
    pub(crate) fn raw_term(&mut self) -> Result<String, MathError> {
        self.skip_whitespace();
        match self.peek() {
            None => Err(syntax("missing argument")),
            Some('{') => self.raw_balanced('{', '}'),
            Some('\\') => {
                self.pos += 1;
                Ok(format!("\\{}", self.control_sequence()?))
            }
            Some(c) => {
                self.pos += 1;
                Ok(c.to_string())
            }
        }
    }

    /// Raw text from an opening `open` to its matching `close`, both included,
    /// with whitespace runs collapsed.
    pub(crate) fn raw_balanced(&mut self, open: char, close: char) -> Result<String, MathError> {
        let mut out = String::new();
        let mut depth = 0usize;
        while let Some(c) = self.bump() {
            if c == '\\' {
                out.push(c);
                if let Some(next) = self.bump() {
                    out.push(next);
                }
                continue;
            }
            if c.is_whitespace() {
                if !out.ends_with(' ') {
                    out.push(' ');
                }
                continue;
            }
            out.push(c);
            if c == open || (open != '{' && c == '{') {
                depth += 1;
            } else if c == close || (open != '{' && c == '}') {
                depth -= 1;
                if depth == 0 {
                    return Ok(out);
                }
            }
        }
        Err(syntax(format!("unclosed `{open}`")))
    }

    /// Raw `[...]` if present.
    pub(crate) fn raw_optional(&mut self) -> Result<Option<String>, MathError> {
        self.skip_whitespace();
        if self.peek() == Some('[') {
            Ok(Some(self.raw_balanced('[', ']')?))
        } else {
            Ok(None)
        }
    }

    /// Raw arguments of a command with arity `arity`.
    pub(crate) fn raw_arguments(&mut self, arity: Arity) -> Result<String, MathError> {
        let mut out = String::new();
        match arity {
            Arity::Terms(n) => {
                for _ in 0..n {
                    out.push_str(&self.raw_term()?);
                }
            }
            Arity::OptionalThenTerm => {
                out.push_str(&self.raw_optional()?.unwrap_or_default());
                out.push_str(&self.raw_term()?);
            }
            Arity::Optional => out.push_str(&self.raw_optional()?.unwrap_or_default()),
            _ => {}
        }
        Ok(out)
    }
}
