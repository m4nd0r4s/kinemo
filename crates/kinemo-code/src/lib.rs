//! Highlighted, morphable source code for kinemo (`k.Code`).
//!
//! Pipeline: `languages` (name -> tree-sitter grammar + queries) ->
//! `highlight` (tree-sitter-highlight, highlight names -> `TokenKind`) ->
//! `tokens` (stable tokens: leaf nodes, never spanning lines, no whitespace)
//! -> `layout` (monospace outlines via kinemo-text, block centered at the
//! origin, y-up) -> `cache`. `diff` matches tokens between two versions for
//! a code morph (line LCS first, then token LCS inside changed regions), and
//! `palette` colors token kinds.
//!
//! ```
//! let layout = kinemo_code::layout_code("x = 1\n", "python", &Default::default()).unwrap();
//! let token = &layout.tokens[layout.glyphs[0].token];
//! assert_eq!(token.text, "x");
//! ```

mod cache;
mod diff;
mod error;
mod highlight;
mod languages;
mod layout;
mod palette;
mod tokens;

pub use cache::layout_code;
pub use diff::match_tokens;
pub use error::CodeError;
pub use languages::{supported_languages, Language};
pub use layout::{CodeGlyph, CodeLayout, CodeOptions};
pub use palette::{Color, Palette};
pub use tokens::{tokenize, Token, TokenKind};
