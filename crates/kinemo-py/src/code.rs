//! Language lookup for `k.Code`, so an unknown `lang=` is an error when the object is made,
//! and highlighted tokens for the dev editor's code view.

use pyo3::prelude::*;

use kinemo_code::{supported_languages, tokenize, Language, TokenKind};

/// Canonical name of a language name or alias (`"py"` -> `"python"`), or `None`.
#[pyfunction]
pub fn code_language(name: &str) -> Option<&'static str> {
    Language::from_name(name).map(Language::name)
}

/// `(text, kind, start_char, end_char)` of every highlighted token of `source` (whitespace is not
/// a token); `kind` is lowercase (`keyword`, `string`, ...). An unknown language is plain text.
#[pyfunction]
pub fn code_tokens(source: &str, language: &str) -> Vec<(String, &'static str, usize, usize)> {
    let tokens = tokenize(source, language).or_else(|_| tokenize(source, "text")).unwrap_or_default();
    tokens.into_iter().map(|t| (t.text, kind_name(t.kind), t.start_char, t.end_char)).collect()
}

fn kind_name(kind: TokenKind) -> &'static str {
    match kind {
        TokenKind::Keyword => "keyword",
        TokenKind::Function => "function",
        TokenKind::Type => "type",
        TokenKind::String => "string",
        TokenKind::Number => "number",
        TokenKind::Comment => "comment",
        TokenKind::Operator => "operator",
        TokenKind::Punctuation => "punctuation",
        TokenKind::Variable => "variable",
        TokenKind::Constant => "constant",
        TokenKind::Plain => "plain",
    }
}

/// Canonical names of every language `k.Code` highlights.
#[pyfunction]
pub fn code_languages() -> Vec<&'static str> {
    supported_languages()
}
