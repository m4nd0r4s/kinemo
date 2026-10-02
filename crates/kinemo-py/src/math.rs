//! Math queries for `k.Math`: validation (K0801), the part tree and subexpression lookup.

use pyo3::prelude::*;
use serde_json::json;

use kinemo_math::{find, glyphs_of, layout_math, named, rules_of, MathError, MathLayout, MathOptions};

use crate::builder::Builder;

fn options(size: f64, display: bool) -> MathOptions {
    MathOptions { size, display }
}

/// Source glyph indices of a node's subtree: glyphs, then rules offset by the glyph count.
fn subtree_indices(lay: &MathLayout, node: usize) -> Vec<usize> {
    let mut out = glyphs_of(lay, node);
    out.extend(rules_of(lay, node).into_iter().map(|r| lay.glyphs.len() + r));
    out
}

#[pymethods]
impl Builder {
    /// `None` when `tex` lays out; otherwise `(code, message, command)`.
    #[pyo3(signature = (tex, size = 0.6, display = true))]
    fn math_error(&self, tex: &str, size: f64, display: bool) -> Option<(String, String, Option<String>)> {
        match layout_math(tex, &options(size, display)) {
            Ok(_) => None,
            Err(e) => {
                let command = match &e { MathError::Unsupported { command } => Some(command.clone()), _ => None };
                Some((e.code().unwrap_or("K0801").to_string(), e.to_string(), command))
            }
        }
    }

    /// Part tree and glyph→node mapping: `{"parts": [...], "glyph_nodes": [...]}`.
    #[pyo3(signature = (tex, size = 0.6, display = true))]
    fn math_info(&self, tex: &str, size: f64, display: bool) -> String {
        let Ok(lay) = layout_math(tex, &options(size, display)) else { return "{}".into() };
        let parts: Vec<serde_json::Value> = lay
            .parts
            .iter()
            .map(|p| json!({"parent": p.parent, "name": p.name, "tex": p.tex, "children": p.children}))
            .collect();
        let mut nodes: Vec<usize> = lay.glyphs.iter().map(|g| g.node).collect();
        nodes.extend(lay.rules.iter().map(|(_, n)| *n));
        let subtrees: Vec<Vec<usize>> = (0..lay.parts.len()).map(|n| subtree_indices(&lay, n)).collect();
        json!({"parts": parts, "glyph_nodes": nodes, "subtrees": subtrees}).to_string()
    }

    /// Glyph indices of every match of `query`: a `\id` name, else a TeX subexpression.
    #[pyo3(signature = (tex, query, size = 0.6, display = true))]
    fn math_find(&self, tex: &str, query: &str, size: f64, display: bool) -> Vec<Vec<usize>> {
        let Ok(lay) = layout_math(tex, &options(size, display)) else { return vec![] };
        if let Some(node) = named(&lay, query) {
            return vec![subtree_indices(&lay, node)];
        }
        find(&lay, query).into_iter().map(|n| subtree_indices(&lay, n)).collect()
    }
}
