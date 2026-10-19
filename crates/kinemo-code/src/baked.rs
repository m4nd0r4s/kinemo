//! Tokens computed ahead of time, for builds without the tree-sitter grammars (the WASM
//! player).
//!
//! A lesson export records every block its frames lay out ([`start_recording`], then
//! [`recorded`] as JSON); the player registers that JSON ([`register`]) before the first frame,
//! and tokenizing reads from it.

use std::collections::{HashMap, HashSet};
use std::sync::{Mutex, OnceLock};

use serde::{Deserialize, Serialize};

use crate::languages::{resolve, Language};
use crate::tokens::{Token, TokenKind};

type Key = (String, Language);

#[derive(Default)]
struct State {
    recording: Option<HashSet<Key>>,
    tokens: HashMap<Key, Vec<Token>>,
}

fn state() -> &'static Mutex<State> {
    static STATE: OnceLock<Mutex<State>> = OnceLock::new();
    STATE.get_or_init(Default::default)
}

/// Remember every block tokenized from now on (see [`recorded`]).
pub fn start_recording() {
    state().lock().unwrap_or_else(|e| e.into_inner()).recording = Some(HashSet::new());
}

pub(crate) fn note(source: &str, language: Language) {
    if let Some(seen) = state().lock().unwrap_or_else(|e| e.into_inner()).recording.as_mut() {
        seen.insert((source.to_owned(), language));
    }
}

/// The blocks tokenized since [`start_recording`], with their tokens, as JSON; stops recording.
pub fn recorded() -> String {
    let seen = state().lock().unwrap_or_else(|e| e.into_inner()).recording.take().unwrap_or_default();
    let mut entries: Vec<Entry> = seen
        .into_iter()
        .filter_map(|(source, language)| {
            let tokens = crate::tokens::tokenize_language(&source, language).ok()?;
            let tokens = tokens.into_iter().map(|t| (t.text, t.kind.name().to_owned(), t.line, t.start_char, t.end_char)).collect();
            Some(Entry { source, language: language.name().to_owned(), tokens })
        })
        .collect();
    entries.sort_by(|a, b| (&a.source, &a.language).cmp(&(&b.source, &b.language)));
    serde_json::to_string(&entries).unwrap_or_else(|_| "[]".into())
}

/// Use the tokens in `json` (from [`recorded`]) from now on.
pub fn register(json: &str) -> Result<(), serde_json::Error> {
    let entries: Vec<Entry> = serde_json::from_str(json)?;
    let mut state = state().lock().unwrap_or_else(|e| e.into_inner());
    for entry in entries {
        let Ok(language) = resolve(&entry.language) else { continue };
        let tokens = entry
            .tokens
            .into_iter()
            .map(|(text, kind, line, start_char, end_char)| Token {
                text,
                kind: TokenKind::from_name(&kind).unwrap_or(TokenKind::Plain),
                line,
                start_char,
                end_char,
            })
            .collect();
        state.tokens.insert((entry.source, language), tokens);
    }
    Ok(())
}

#[cfg_attr(feature = "grammars", allow(dead_code))]
pub(crate) fn tokens(source: &str, language: Language) -> Option<Vec<Token>> {
    state().lock().unwrap_or_else(|e| e.into_inner()).tokens.get(&(source.to_owned(), language)).cloned()
}

/// One block as shipped: tokens as (text, kind, line, start char, end char).
#[derive(Serialize, Deserialize)]
struct Entry {
    source: String,
    language: String,
    tokens: Vec<(String, String, usize, usize, usize)>,
}

impl TokenKind {
    pub const ALL: [TokenKind; 11] = [
        TokenKind::Keyword,
        TokenKind::Function,
        TokenKind::Type,
        TokenKind::String,
        TokenKind::Number,
        TokenKind::Comment,
        TokenKind::Operator,
        TokenKind::Punctuation,
        TokenKind::Variable,
        TokenKind::Constant,
        TokenKind::Plain,
    ];

    /// Lowercase name, as shipped in a baked token list.
    pub fn name(self) -> &'static str {
        match self {
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

    pub fn from_name(name: &str) -> Option<TokenKind> {
        TokenKind::ALL.into_iter().find(|kind| kind.name() == name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(feature = "grammars")]
    #[test]
    fn recorded_tokens_round_trip() {
        start_recording();
        let source = "def f(x):\n    return 2 * x  # double\n";
        let original = crate::tokenize(source, "python").unwrap();
        let json = recorded();
        register(&json).unwrap();
        assert_eq!(tokens(source, Language::Python), Some(original));
    }

    #[test]
    fn kind_names_round_trip() {
        for kind in TokenKind::ALL {
            assert_eq!(TokenKind::from_name(kind.name()), Some(kind));
        }
    }
}
