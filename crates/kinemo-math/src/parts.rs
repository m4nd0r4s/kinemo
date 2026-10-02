//! Part tree construction and marker emission.
//!
//! Every part-tree node except the root is emitted wrapped in a marker,
//! `\textcolor{<node id>}{...}` (user `\textcolor`s are dropped by the parser).
//! mitex converts it to `colortext(<id digits>, body)`, which the prelude
//! defines as `text(fill: <color encoding the id>, body)`.
//! Fill is a pure style: it reaches every glyph and rule inside the node but
//! does not change math layout (classes, spacing and limits are preserved;
//! see the `markers_do_not_move_glyphs` test). After layout, a glyph's fill
//! color identifies its innermost node; unmarked ink (plain black) belongs to
//! the root.

use crate::latex_parser::Ast;
use crate::normalize::{list_tex, single_tex};
use crate::types::PartNode;

/// Environments whose `&` column gets LaTeX's quad of space.
const CASES_ENVIRONMENTS: &[&str] = &["cases", "dcases", "rcases"];

/// Delimiters that are ordinary symbols in LaTeX when used bare (`|x|`). typst
/// would pair them into stretchy fences with extra spacing, so they are
/// emitted as `\mathord{...}`.
const ORDINARY_DELIMITERS: &[&str] = &["|", "\\|", "\\vert", "\\Vert", "\\lvert", "\\rvert", "\\lVert", "\\rVert"];

/// The part tree of a formula plus the LaTeX to hand to mitex.
pub(crate) struct PartTree {
    pub(crate) parts: Vec<PartNode>,
    /// LaTeX with every non-root node wrapped in its marker (or plain when
    /// built with `marked = false`).
    pub(crate) latex: String,
    /// (base atom node, script node) pairs where the primes were emitted inside
    /// the base's marker; prime glyphs found in the base belong to the script.
    pub(crate) prime_bases: Vec<(usize, usize)>,
}

/// Build the part tree of `items`. With `marked = false` the emitted LaTeX has
/// no markers (same structure otherwise), which is used to verify that markers
/// do not change the layout.
pub(crate) fn build(items: &[Ast], marked: bool) -> PartTree {
    let root = PartNode { parent: None, name: None, tex: list_tex(items), children: Vec::new() };
    let mut builder = Builder { parts: vec![root], marked, prime_bases: Vec::new() };
    let latex = builder.list(0, items);
    PartTree { parts: builder.parts, latex, prime_bases: builder.prime_bases }
}

struct Builder {
    parts: Vec<PartNode>,
    marked: bool,
    prime_bases: Vec<(usize, usize)>,
}

impl Builder {
    fn add(&mut self, parent: usize, tex: String) -> usize {
        let id = self.parts.len();
        self.parts.push(PartNode { parent: Some(parent), name: None, tex, children: Vec::new() });
        self.parts[parent].children.push(id);
        id
    }

    fn wrap(&self, id: usize, inner: &str) -> String {
        if self.marked {
            format!("\\textcolor{{{id}}}{{{inner}}}")
        } else {
            inner.to_owned()
        }
    }

    fn list(&mut self, parent: usize, items: &[Ast]) -> String {
        let pieces: Vec<String> = items.iter().map(|item| self.item(parent, item)).collect();
        pieces.join(" ")
    }

    /// A list that forms one node (a group, an argument, an `\id` body). A list
    /// of exactly one item is that item's node (its braces are redundant).
    fn group(&mut self, parent: usize, items: &[Ast], name: Option<&str>) -> String {
        let single = items.len() == 1 && !matches!(items[0], Ast::Raw { .. } | Ast::Id { .. });
        if single {
            let first_new = self.parts.len();
            let out = self.item(parent, &items[0]);
            if let Some(name) = name {
                self.parts[first_new].name = Some(name.to_owned());
            }
            return out;
        }
        if items.is_empty() && name.is_none() {
            return String::new();
        }
        let id = self.add(parent, list_tex(items));
        self.parts[id].name = name.map(str::to_owned);
        let inner = self.list(id, items);
        self.wrap(id, &inner)
    }

    fn item(&mut self, parent: usize, item: &Ast) -> String {
        match item {
            Ast::Raw { tex, .. } => tex.clone(),
            Ast::Atom(tex) => {
                let id = self.add(parent, tex.clone());
                if ORDINARY_DELIMITERS.contains(&tex.as_str()) {
                    return self.wrap(id, &format!("\\mathord{{{tex}}}"));
                }
                self.wrap(id, tex)
            }
            Ast::Group(items) => self.group(parent, items, None),
            Ast::Id { name, body } => self.group(parent, body, Some(name)),
            Ast::Command { name, raw_args, args } => {
                let id = self.add(parent, single_tex(item));
                let mut inner = format!("\\{name}{raw_args}");
                for arg in args {
                    let emitted = self.group(id, arg, None);
                    inner.push_str(&format!("{{{emitted}}}"));
                }
                self.wrap(id, &inner)
            }
            Ast::Script { base, primes, limits, sub, sup } => {
                let id = self.add(parent, single_tex(item));
                let primes = "'".repeat(*primes);
                let mut inner = match base.as_deref() {
                    // typst skips a styled base's italic correction for primes,
                    // so primes of a single atom go inside the atom's marker.
                    Some(Ast::Atom(tex)) if !primes.is_empty() => {
                        let base_id = self.add(id, tex.clone());
                        self.prime_bases.push((base_id, id));
                        self.wrap(base_id, &format!("{tex}{primes}"))
                    }
                    Some(base) => self.item(id, base) + &primes,
                    None => format!("{{}}{primes}"),
                };
                if let Some(limits) = limits {
                    inner.push_str(&format!(" {limits} "));
                }
                if let Some(sub) = sub {
                    let emitted = self.group(id, sub, None);
                    inner.push_str(&format!("_{{{emitted}}}"));
                }
                if let Some(sup) = sup {
                    let emitted = self.group(id, sup, None);
                    inner.push_str(&format!("^{{{emitted}}}"));
                }
                self.wrap(id, &inner)
            }
            Ast::LeftRight { left, right, body } => {
                let id = self.add(parent, single_tex(item));
                let body = self.list(id, body);
                self.wrap(id, &format!("\\left{left} {body} \\right{right}"))
            }
            Ast::Environment { name, args, body } => {
                let id = self.add(parent, single_tex(item));
                let mut body = self.list(id, body);
                if CASES_ENVIRONMENTS.contains(&name.as_str()) {
                    // LaTeX separates the value and condition columns by a quad;
                    // typst's `cases` only aligns at `&`.
                    body = body.replace(" & ", " & \\quad ");
                }
                self.wrap(id, &format!("\\begin{{{name}}}{args} {body} \\end{{{name}}}"))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::latex_parser::parse;

    #[test]
    fn tree_of_pythagoras() {
        let tree = build(&parse(r"\id{lhs}{a^2 + b^2} = c^2").unwrap(), true);
        let texs: Vec<&str> = tree.parts.iter().map(|p| p.tex.as_str()).collect();
        assert_eq!(texs[0], "a^{2}+b^{2}=c^{2}");
        let lhs = tree.parts.iter().position(|p| p.name.as_deref() == Some("lhs")).unwrap();
        assert_eq!(tree.parts[lhs].tex, "a^{2}+b^{2}");
        assert_eq!(tree.parts[lhs].children.len(), 3);
        assert!(texs.contains(&"c^{2}"));
        assert!(tree.latex.starts_with(r"\textcolor{1}{"), "{}", tree.latex);
        for (i, p) in tree.parts.iter().enumerate() {
            for &c in &p.children {
                assert_eq!(tree.parts[c].parent, Some(i));
            }
        }
    }

    #[test]
    fn single_item_groups_collapse() {
        let tree = build(&parse(r"\frac{a}{b+c}").unwrap(), true);
        // root, frac, a, group b+c, b, +, c
        assert_eq!(tree.parts.len(), 7);
        assert_eq!(tree.parts[2].tex, "a");
        assert_eq!(tree.parts[3].tex, "b+c");
    }
}
