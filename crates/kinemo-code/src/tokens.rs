//! Tokens: stable, highlighted units of source code.
//!
//! Token boundaries come from tree-sitter leaf nodes, highlight changes and
//! whitespace. String and comment runs stay whole on each line (internal
//! spaces included) so they travel as one unit in a morph. Tokens never span
//! lines and whitespace is never a token.

use std::cell::RefCell;

use tree_sitter::Parser;

use crate::highlight::byte_kinds;
use crate::languages::{resolve, Language};
use crate::CodeError;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum TokenKind {
    Keyword,
    Function,
    Type,
    String,
    Number,
    Comment,
    Operator,
    Punctuation,
    Variable,
    Constant,
    Plain,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Token {
    pub text: String,
    pub kind: TokenKind,
    /// Zero-based line (lines are separated by '\n').
    pub line: usize,
    /// Char range `[start_char, end_char)` in the whole source.
    pub start_char: usize,
    pub end_char: usize,
}

/// Split `source` into highlighted tokens. Fails only for an unknown language.
pub fn tokenize(source: &str, language: &str) -> Result<Vec<Token>, CodeError> {
    tokenize_language(source, resolve(language)?)
}

pub(crate) fn tokenize_language(source: &str, language: Language) -> Result<Vec<Token>, CodeError> {
    let chars: Vec<char> = source.chars().collect();
    let byte_to_char = byte_to_char_table(source);
    let kinds_by_byte = byte_kinds(source, language)?;
    let kinds: Vec<TokenKind> = source
        .char_indices()
        .map(|(byte, _)| kinds_by_byte[byte])
        .collect();
    let boundaries = match language.grammar() {
        Some(grammar) => leaf_boundaries(source, grammar, &byte_to_char, chars.len()),
        None => character_class_boundaries(&chars),
    };
    let mut tokens = split_tokens(&chars, &kinds, &boundaries);
    if language != Language::PlainText {
        for token in &mut tokens {
            token.kind = refine_kind(&token.text, token.kind);
        }
    }
    Ok(tokens)
}

/// Fill gaps left by the bundled queries: numeric constants become `Number`
/// (Rust highlights integers as constants), unhighlighted symbols become
/// `Punctuation` (brackets, separators) or `Operator`, and unhighlighted
/// identifiers become `Variable`.
fn refine_kind(text: &str, kind: TokenKind) -> TokenKind {
    let first = text.chars().next().unwrap_or(' ');
    match kind {
        TokenKind::Constant if first.is_ascii_digit() => TokenKind::Number,
        TokenKind::Plain if text.chars().all(|c| "()[]{},;:.".contains(c)) => {
            TokenKind::Punctuation
        }
        TokenKind::Plain if text.chars().all(|c| c.is_ascii_punctuation()) => TokenKind::Operator,
        TokenKind::Plain if text.chars().all(|c| c.is_alphanumeric() || c == '_') => {
            if first.is_ascii_digit() {
                TokenKind::Number
            } else {
                TokenKind::Variable
            }
        }
        other => other,
    }
}

fn byte_to_char_table(source: &str) -> Vec<usize> {
    let mut table = vec![0; source.len() + 1];
    let mut char_index = 0;
    for (byte, character) in source.char_indices() {
        table[byte..byte + character.len_utf8()].fill(char_index);
        char_index += 1;
    }
    table[source.len()] = char_index;
    table
}

thread_local! {
    static PARSER: RefCell<Parser> = RefCell::new(Parser::new());
}

/// `boundary[i]` is true when a tree-sitter leaf starts or ends at char `i`.
fn leaf_boundaries(
    source: &str,
    grammar: tree_sitter::Language,
    byte_to_char: &[usize],
    char_count: usize,
) -> Vec<bool> {
    let mut boundaries = vec![false; char_count + 1];
    let tree = PARSER.with(|cell| {
        let mut parser = cell.borrow_mut();
        parser.set_language(&grammar).ok()?;
        parser.parse(source, None)
    });
    let Some(tree) = tree else { return boundaries };
    let mut cursor = tree.walk();
    'walk: loop {
        let node = cursor.node();
        if node.child_count() == 0 {
            boundaries[byte_to_char[node.start_byte()]] = true;
            boundaries[byte_to_char[node.end_byte()]] = true;
        }
        if cursor.goto_first_child() {
            continue;
        }
        while !cursor.goto_next_sibling() {
            if !cursor.goto_parent() {
                break 'walk;
            }
        }
    }
    boundaries
}

/// Plain text: split between word characters and symbols; each symbol alone.
fn character_class_boundaries(chars: &[char]) -> Vec<bool> {
    let is_word = |character: char| character.is_alphanumeric() || character == '_';
    let mut boundaries = vec![false; chars.len() + 1];
    for index in 1..chars.len() {
        boundaries[index] = !(is_word(chars[index - 1]) && is_word(chars[index]));
    }
    boundaries
}

fn split_tokens(chars: &[char], kinds: &[TokenKind], boundaries: &[bool]) -> Vec<Token> {
    let mut tokens = Vec::new();
    let mut push = |start: usize, end: usize, line: usize| {
        tokens.push(Token {
            text: chars[start..end].iter().collect(),
            kind: kinds[start],
            line,
            start_char: start,
            end_char: end,
        });
    };
    let mut line = 0;
    let mut index = 0;
    while index < chars.len() {
        let character = chars[index];
        if character == '\n' {
            line += 1;
            index += 1;
            continue;
        }
        if character.is_whitespace() {
            index += 1;
            continue;
        }
        let kind = kinds[index];
        let mut end = index + 1;
        if matches!(kind, TokenKind::String | TokenKind::Comment) {
            while end < chars.len() && chars[end] != '\n' && kinds[end] == kind {
                end += 1;
            }
            let next = end;
            while chars[end - 1].is_whitespace() {
                end -= 1;
            }
            push(index, end, line);
            index = next;
        } else {
            while end < chars.len()
                && !chars[end].is_whitespace()
                && kinds[end] == kind
                && !boundaries[end]
            {
                end += 1;
            }
            push(index, end, line);
            index = end;
        }
    }
    tokens
}
