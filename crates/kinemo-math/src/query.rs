//! Part lookups: by TeX subexpression, by `\id` name, and glyphs of a subtree.

use crate::latex_parser::parse;
use crate::normalize::list_tex;
use crate::types::MathLayout;

/// Normalized TeX of `tex` (as stored in [`crate::PartNode::tex`]), or `None`
/// if it does not parse.
pub fn normalize_tex(tex: &str) -> Option<String> {
    parse(tex).ok().map(|ast| list_tex(&ast))
}

/// Ids of the nodes whose normalized TeX equals the normalized `tex_query`, in
/// tree pre-order. Matching is by syntax tree: `c^2` and `c^{2}` are the same.
pub fn find(layout: &MathLayout, tex_query: &str) -> Vec<usize> {
    let Some(query) = normalize_tex(tex_query) else { return Vec::new() };
    if query.is_empty() {
        return Vec::new();
    }
    layout.parts.iter().enumerate().filter(|(_, p)| p.tex == query).map(|(i, _)| i).collect()
}

/// The node named `name` with `\id{name}{...}` (the first one, if repeated).
pub fn named(layout: &MathLayout, name: &str) -> Option<usize> {
    layout.parts.iter().position(|p| p.name.as_deref() == Some(name))
}

/// True if `node` is `ancestor` or inside its subtree.
fn is_within(layout: &MathLayout, mut node: usize, ancestor: usize) -> bool {
    loop {
        if node == ancestor {
            return true;
        }
        match layout.parts.get(node).and_then(|p| p.parent) {
            Some(parent) => node = parent,
            None => return false,
        }
    }
}

/// Indices (into [`MathLayout::glyphs`]) of all glyphs in the subtree of `node`.
pub fn glyphs_of(layout: &MathLayout, node: usize) -> Vec<usize> {
    if node >= layout.parts.len() {
        return Vec::new();
    }
    (0..layout.glyphs.len()).filter(|&g| is_within(layout, layout.glyphs[g].node, node)).collect()
}

/// Indices (into [`MathLayout::rules`]) of all rules in the subtree of `node`.
pub fn rules_of(layout: &MathLayout, node: usize) -> Vec<usize> {
    if node >= layout.parts.len() {
        return Vec::new();
    }
    (0..layout.rules.len()).filter(|&r| is_within(layout, layout.rules[r].1, node)).collect()
}
