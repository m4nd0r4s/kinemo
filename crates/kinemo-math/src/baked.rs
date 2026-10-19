//! Layouts computed ahead of time, for builds without typst (the WASM player).
//!
//! A lesson export records every formula its frames lay out ([`start_recording`], then
//! [`recorded`] as JSON); the player registers that JSON ([`register`]) before the first frame,
//! and [`crate::layout_math`] reads from it.

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex, OnceLock};

use kurbo::{BezPath, Rect};
use serde::{Deserialize, Serialize};

use crate::types::{MathGlyph, MathLayout, MathOptions, PartNode};

type Key = (String, u64, bool);

fn key(tex: &str, opts: &MathOptions) -> Key {
    (tex.to_owned(), opts.size.to_bits(), opts.display)
}

#[derive(Default)]
struct State {
    recording: Option<HashSet<Key>>,
    layouts: HashMap<Key, MathLayout>,
}

fn state() -> &'static Mutex<State> {
    static STATE: OnceLock<Mutex<State>> = OnceLock::new();
    STATE.get_or_init(Default::default)
}

/// Remember every formula laid out from now on (see [`recorded`]).
pub fn start_recording() {
    state().lock().unwrap_or_else(|e| e.into_inner()).recording = Some(HashSet::new());
}

pub(crate) fn note(tex: &str, opts: &MathOptions) {
    if let Some(seen) = state().lock().unwrap_or_else(|e| e.into_inner()).recording.as_mut() {
        seen.insert(key(tex, opts));
    }
}

/// The formulas laid out since [`start_recording`], with their layouts, as JSON; stops recording.
pub fn recorded() -> String {
    let seen = state().lock().unwrap_or_else(|e| e.into_inner()).recording.take().unwrap_or_default();
    let mut entries: Vec<Entry> = seen
        .into_iter()
        .filter_map(|(tex, size, display)| {
            let opts = MathOptions { size: f64::from_bits(size), display };
            crate::layout_math(&tex, &opts).ok().map(|layout| Entry::new(tex, &opts, &layout))
        })
        .collect();
    entries.sort_by(|a, b| (&a.tex, a.size.to_bits(), a.display).cmp(&(&b.tex, b.size.to_bits(), b.display)));
    serde_json::to_string(&entries).unwrap_or_else(|_| "[]".into())
}

/// Use the layouts in `json` (from [`recorded`]) from now on.
pub fn register(json: &str) -> Result<(), serde_json::Error> {
    let entries: Vec<Entry> = serde_json::from_str(json)?;
    let mut state = state().lock().unwrap_or_else(|e| e.into_inner());
    for entry in entries {
        let opts = MathOptions { size: entry.size, display: entry.display };
        state.layouts.insert(key(&entry.tex, &opts), entry.layout());
    }
    Ok(())
}

#[cfg_attr(feature = "typeset", allow(dead_code))]
pub(crate) fn layout(tex: &str, opts: &MathOptions) -> Option<MathLayout> {
    state().lock().unwrap_or_else(|e| e.into_inner()).layouts.get(&key(tex, opts)).cloned()
}

/// One formula as shipped: paths as SVG path data.
#[derive(Serialize, Deserialize)]
struct Entry {
    tex: String,
    size: f64,
    display: bool,
    glyphs: Vec<(String, usize)>,
    rules: Vec<(String, usize)>,
    parts: Vec<Part>,
    bbox: [f64; 4],
    baseline: f64,
}

#[derive(Serialize, Deserialize)]
struct Part {
    parent: Option<usize>,
    name: Option<String>,
    tex: String,
    children: Vec<usize>,
}

impl Entry {
    fn new(tex: String, opts: &MathOptions, layout: &Arc<MathLayout>) -> Entry {
        Entry {
            tex,
            size: opts.size,
            display: opts.display,
            glyphs: layout.glyphs.iter().map(|g| (g.path.to_svg(), g.node)).collect(),
            rules: layout.rules.iter().map(|(path, node)| (path.to_svg(), *node)).collect(),
            parts: layout
                .parts
                .iter()
                .map(|p| Part { parent: p.parent, name: p.name.clone(), tex: p.tex.clone(), children: p.children.clone() })
                .collect(),
            bbox: [layout.bbox.x0, layout.bbox.y0, layout.bbox.x1, layout.bbox.y1],
            baseline: layout.baseline,
        }
    }

    fn layout(self) -> MathLayout {
        let path = |svg: &str| BezPath::from_svg(svg).unwrap_or_default();
        MathLayout {
            glyphs: self.glyphs.iter().map(|(svg, node)| MathGlyph { path: path(svg), node: *node }).collect(),
            rules: self.rules.iter().map(|(svg, node)| (path(svg), *node)).collect(),
            parts: self
                .parts
                .into_iter()
                .map(|p| PartNode { parent: p.parent, name: p.name, tex: p.tex, children: p.children })
                .collect(),
            bbox: Rect::new(self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3]),
            baseline: self.baseline,
        }
    }
}

#[cfg(all(test, feature = "typeset"))]
mod tests {
    use super::*;

    #[test]
    fn a_recorded_layout_round_trips() {
        start_recording();
        let opts = MathOptions { size: 0.7, display: true };
        let original = crate::layout_math(r"\frac{a}{b^2}", &opts).unwrap();
        let json = recorded();
        let entries: Vec<Entry> = serde_json::from_str(&json).unwrap();
        let entry = entries.into_iter().find(|e| e.tex == r"\frac{a}{b^2}").unwrap();
        let back = entry.layout();
        assert_eq!(back.glyphs.len(), original.glyphs.len());
        assert_eq!(back.rules.len(), original.rules.len());
        assert_eq!(back.parts, original.parts);
        assert_eq!(back.bbox, original.bbox);
        for (a, b) in back.glyphs.iter().zip(&original.glyphs) {
            assert_eq!(a.node, b.node);
            let (ra, rb) = (kurbo::Shape::bounding_box(&a.path), kurbo::Shape::bounding_box(&b.path));
            assert!((ra.x0 - rb.x0).abs() < 1e-9 && (ra.y1 - rb.y1).abs() < 1e-9);
        }
    }
}
