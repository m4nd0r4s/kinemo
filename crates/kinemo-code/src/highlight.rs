//! Tree-sitter highlighting: one compiled configuration per language, and a
//! per-char `TokenKind` classification of a source string.

use std::cell::RefCell;
use std::sync::OnceLock;

use tree_sitter_highlight::{HighlightConfiguration, HighlightEvent, Highlighter};

use crate::languages::Language;
use crate::tokens::TokenKind;
use crate::CodeError;

/// Highlight names recognized in the bundled queries, with their kind.
/// tree-sitter-highlight matches a capture to the longest dotted prefix in
/// this list, so `@function.method` falls back to `function`.
const HIGHLIGHT_NAMES: &[(&str, TokenKind)] = &[
    ("attribute", TokenKind::Constant),
    ("boolean", TokenKind::Constant),
    ("character", TokenKind::String),
    ("comment", TokenKind::Comment),
    ("constant", TokenKind::Constant),
    ("constant.builtin", TokenKind::Constant),
    ("constructor", TokenKind::Type),
    ("delimiter", TokenKind::Punctuation),
    ("embedded", TokenKind::Plain),
    ("escape", TokenKind::String),
    ("float", TokenKind::Number),
    ("function", TokenKind::Function),
    ("keyword", TokenKind::Keyword),
    ("label", TokenKind::Variable),
    ("module", TokenKind::Type),
    ("number", TokenKind::Number),
    ("operator", TokenKind::Operator),
    ("property", TokenKind::Variable),
    ("punctuation", TokenKind::Punctuation),
    ("string", TokenKind::String),
    ("string.special.key", TokenKind::Variable),
    ("tag", TokenKind::Type),
    ("type", TokenKind::Type),
    ("variable", TokenKind::Variable),
    ("variable.builtin", TokenKind::Keyword),
];

fn compile_configuration(language: Language) -> Result<HighlightConfiguration, CodeError> {
    let grammar = language
        .grammar()
        .expect("plain text has no highlight configuration");
    let mut configuration = HighlightConfiguration::new(
        grammar,
        language.name(),
        &language.highlights_query(),
        "",
        &language.locals_query(),
    )
    .map_err(|error| CodeError::Query {
        language: language.name().to_owned(),
        message: error.to_string(),
    })?;
    let names: Vec<&str> = HIGHLIGHT_NAMES.iter().map(|(name, _)| *name).collect();
    configuration.configure(&names);
    Ok(configuration)
}

/// Compiled configuration for `language` (compiled once per process).
fn configuration(language: Language) -> Result<&'static HighlightConfiguration, CodeError> {
    type Slot = OnceLock<Result<HighlightConfiguration, CodeError>>;
    static SLOTS: [Slot; Language::ALL.len()] = [const { OnceLock::new() }; Language::ALL.len()];
    let index = Language::ALL
        .iter()
        .position(|candidate| *candidate == language)
        .unwrap();
    SLOTS[index]
        .get_or_init(|| compile_configuration(language))
        .as_ref()
        .map_err(Clone::clone)
}

thread_local! {
    static HIGHLIGHTER: RefCell<Highlighter> = RefCell::new(Highlighter::new());
}

/// Kind of every byte of `source` (innermost highlight wins; unhighlighted = `Plain`).
pub(crate) fn byte_kinds(source: &str, language: Language) -> Result<Vec<TokenKind>, CodeError> {
    let mut kinds = vec![TokenKind::Plain; source.len()];
    if language == Language::PlainText {
        return Ok(kinds);
    }
    let configuration = configuration(language)?;
    HIGHLIGHTER.with(|cell| {
        let mut highlighter = cell.borrow_mut();
        let events = highlighter
            .highlight(configuration, source.as_bytes(), None, |_| None)
            .map_err(|error| CodeError::Highlight(error.to_string()))?;
        let mut stack: Vec<TokenKind> = Vec::new();
        for event in events {
            match event.map_err(|error| CodeError::Highlight(error.to_string()))? {
                HighlightEvent::HighlightStart(highlight) => {
                    stack.push(HIGHLIGHT_NAMES[highlight.0].1)
                }
                HighlightEvent::HighlightEnd => {
                    stack.pop();
                }
                HighlightEvent::Source { start, end } => {
                    let kind = stack
                        .iter()
                        .rev()
                        .copied()
                        .find(|kind| *kind != TokenKind::Plain);
                    kinds[start..end].fill(kind.unwrap_or(TokenKind::Plain));
                }
            }
        }
        Ok(kinds)
    })
}
