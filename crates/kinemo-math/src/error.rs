//! Errors returned by [`crate::layout_math`].

use std::fmt;

/// Why a formula could not be laid out.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MathError {
    /// A command or environment the embedded engine does not know (spec code `K0801`).
    Unsupported { command: String },
    /// Malformed LaTeX: unbalanced braces, missing arguments, `\left` without `\right`...
    Syntax(String),
    /// The typst engine rejected the converted formula.
    Layout(String),
}

impl MathError {
    /// Spec diagnostic code, when there is one.
    pub fn code(&self) -> Option<&'static str> {
        match self {
            MathError::Unsupported { .. } => Some("K0801"),
            _ => None,
        }
    }
}

impl fmt::Display for MathError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MathError::Unsupported { command } => write!(
                f,
                "K0801: unsupported command `{command}` in the embedded math engine; \
                 use engine=\"tex\" for a real LaTeX installation"
            ),
            MathError::Syntax(msg) => write!(f, "math syntax error: {msg}"),
            MathError::Layout(msg) => write!(f, "math layout error: {msg}"),
        }
    }
}

impl std::error::Error for MathError {}
