//! Error type for code tokenizing and layout.

use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CodeError {
    /// The language name (or alias) is not supported. Carries the name given.
    UnknownLanguage(String),
    /// A bundled highlight query failed to compile (a bug in this crate).
    Query { language: String, message: String },
    /// Tree-sitter could not parse or highlight the source.
    Highlight(String),
}

impl fmt::Display for CodeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CodeError::UnknownLanguage(name) => write!(
                formatter,
                "unknown code language '{name}' (supported: {})",
                crate::languages::supported_languages().join(", ")
            ),
            CodeError::Query { language, message } => {
                write!(
                    formatter,
                    "highlight query for '{language}' failed to compile: {message}"
                )
            }
            CodeError::Highlight(message) => write!(formatter, "highlighting failed: {message}"),
        }
    }
}

impl std::error::Error for CodeError {}
