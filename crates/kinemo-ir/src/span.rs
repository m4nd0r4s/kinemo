//! Source locations attached to every IR node.

use serde::{Deserialize, Serialize};

/// Source location captured at construction time. `col` is a 0-based character index;
/// a span covering an expression (the user's call) also has its exclusive end.
#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct Span {
    pub file: String,
    pub line: u32,
    #[serde(default)]
    pub col: u32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub end_line: u32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub end_col: u32,
}

fn is_zero(value: &u32) -> bool {
    *value == 0
}

