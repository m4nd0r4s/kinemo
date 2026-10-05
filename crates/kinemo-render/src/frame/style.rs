//! Style resolution of a leaf: colors, opacity chain, entry effects → draw items.

use kurbo::BezPath;

use kinemo_eval::color;
use kinemo_ir::ObjectId;
use kinemo_layout::{Layout, PartRole};

use super::reveal::{arrow_part_progress, fill_fraction, glyph_progress, outline_fraction};
use super::FrameSize;
use crate::geom::trim;
use crate::raster::{Cap, DrawItem, Fill, Join, Stroke};

/// Style inherited down the tree (opacity multiplies, tint takes the strongest).
pub(crate) struct Inherited {
    pub(crate) opacity: f64,
    pub(crate) tint: Option<([f64; 4], f64)>,
}

pub(crate) fn inherited(layout: &Layout, leaf: ObjectId, t: f64) -> Inherited {
    let mut opacity = 1.0;
    let mut tint: Option<([f64; 4], f64)> = None;
    let mut cur = Some(leaf);
    while let Some(o) = cur {
        opacity *= layout.prop_f(o, "opacity", t, 1.0) * layout.prop_f(o, "_fade", t, 1.0);
        let amount = layout.prop_f(o, "_tint_amount", t, 0.0);
        if amount > tint.map_or(0.0, |(_, a)| a) {
            if let Some(c) = layout.prop_color(o, "_tint", t) {
                tint = Some((c, amount));
            }
        }
        cur = layout.scene().object(o).parent;
    }
    Inherited { opacity: opacity.clamp(0.0, 1.0), tint }
}

/// Reveal progress (`_draw`, `_write`) is the smallest along the parent chain, so writing
/// a text also writes the glyph runs it is made of.
pub(crate) fn chain_min(layout: &Layout, leaf: ObjectId, prop: &str, t: f64) -> f64 {
    let mut out = 1.0f64;
    let mut cur = Some(leaf);
    while let Some(o) = cur {
        out = out.min(layout.prop_f(o, prop, t, 1.0));
        cur = layout.scene().object(o).parent;
    }
    out
}

fn with_alpha(c: [f64; 4], a: f64) -> [f64; 4] {
    [c[0], c[1], c[2], (c[3] * a).clamp(0.0, 1.0)]
}

fn dash(layout: &Layout, o: ObjectId, t: f64, scale: f64) -> Option<Vec<f64>> {
    let v = layout.prop(o, "dash", t)?;
    let d: Vec<f64> = v.as_list().iter().map(|x| x.as_f64() * scale).filter(|x| *x > 0.0).collect();
    (!d.is_empty()).then_some(d)
}

pub(crate) fn draw_items(layout: &Layout, leaf: ObjectId, t: f64, size: FrameSize) -> Vec<DrawItem> {
    painted_parts(layout, leaf, t, size, Reveal::Animated).into_iter().map(|p| p.item).collect()
}

/// Whether `_draw`/`_write` progress applies (morphs read shapes fully drawn).
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Reveal {
    Animated,
    Full,
}

/// A painted part as morphs see it: the item, its matching key and its glyph index in
/// the text-like source (0 for shapes).
pub(crate) struct PaintedPart {
    pub item: DrawItem,
    pub key: Option<String>,
    pub index: usize,
}

/// One item per painted part, with the part's matching key (morphs pair parts by key).
pub(crate) fn painted_parts(layout: &Layout, leaf: ObjectId, t: f64, size: FrameSize, reveal_mode: Reveal) -> Vec<PaintedPart> {
    let inh = inherited(layout, leaf, t);
    if inh.opacity <= 0.0 && reveal_mode == Reveal::Animated {
        return vec![];
    }
    if layout.scene().object(leaf).kind == "image" {
        return super::image::painted_image(layout, leaf, t, size, reveal_mode, inh.opacity);
    }
    let tinted = |c: [f64; 4]| match inh.tint {
        Some((tc, a)) => color::mix(c, [tc[0], tc[1], tc[2], c[3]], a),
        None => c,
    };
    let to_px = size.pixel_affine(layout.scene()) * layout.render_affine(leaf, t);
    let sscale = size.stroke_scale();

    let fill = layout.prop_color(leaf, "fill", t).map(tinted);
    let fill_opacity = layout.prop_f(leaf, "fill_opacity", t, 0.0);
    let stroke = layout.prop_color(leaf, "stroke", t).map(tinted);
    let stroke_width = layout.prop_f(leaf, "stroke_width", t, 0.0) * sscale;
    let dash = dash(layout, leaf, t, sscale);
    let draw = chain_min(layout, leaf, "_draw", t);
    let write = chain_min(layout, leaf, "_write", t);

    let even_odd = layout.prop_str(leaf, "fill_rule", t).as_deref() == Some("evenodd");
    // Strokes are round unless the object says otherwise (paths imported from SVG do).
    let cap = match layout.prop_str(leaf, "line_cap", t).as_deref() {
        Some("butt") => Cap::Butt,
        Some("square") => Cap::Square,
        _ => Cap::Round,
    };
    let join = match layout.prop_str(leaf, "line_join", t).as_deref() {
        Some("miter") => Join::Miter,
        Some("bevel") => Join::Bevel,
        _ => Join::Round,
    };
    let parts = layout.parts(leaf, t);
    let arrow = layout.scene().object(leaf).kind == "arrow";
    let mut items = Vec::with_capacity(parts.len());
    for part in &parts {
        let progress = match (reveal_mode, part.role) {
            (Reveal::Full, _) => 1.0,
            (_, PartRole::Glyph) => draw.min(glyph_progress(write, part.index, part.count)),
            _ if arrow => arrow_part_progress(draw.min(write), part.index),
            _ => draw.min(write),
        };
        if progress <= 0.0 {
            continue;
        }
        let fills = part.role != PartRole::Open;
        // Syntax colors yield to the leaf's own fill as `recolor` goes to 1.
        let fill = match (part.color, fill) {
            (Some(own), Some(leaf_fill)) => Some(tinted(color::mix(own, leaf_fill, layout.prop_f(leaf, "recolor", t, 0.0)))),
            (Some(own), None) => Some(tinted(own)),
            (None, f) => f,
        };
        let has_fill = fills && fill.is_some() && fill_opacity > 0.0;
        let has_stroke = stroke.is_some() && stroke_width > 0.0;
        let path = to_px * part.path.clone();
        let reveal = progress < 1.0;

        let fill_paint = has_fill.then(|| Fill {
            color: with_alpha(fill.unwrap(), fill_opacity * if reveal { fill_fraction(progress) } else { 1.0 }),
        });
        let stroke_paint = if has_stroke {
            Some(Stroke {
                color: stroke.unwrap(),
                width: stroke_width,
                dash: dash.clone(),
                cap,
                join,
            })
        } else if reveal && has_fill {
            // Shapes without a stroke are traced with their fill color while drawing.
            Some(Stroke {
                color: with_alpha(fill.unwrap(), 1.0 - fill_fraction(progress)),
                width: 2.0 * sscale,
                dash: None,
                cap: Cap::Round,
                join: Join::Round,
            })
        } else {
            None
        };
        if fill_paint.is_none() && stroke_paint.is_none() {
            continue;
        }
        let outline = if reveal { trim(&path, 0.0, outline_fraction(progress)) } else { path.clone() };
        if reveal {
            // Fill uses the whole shape; the traced outline is a separate item.
            if let Some(f) = fill_paint {
                items.push(PaintedPart { item: item(path, Some(f), None, inh.opacity, even_odd), key: part.key.clone(), index: part.index });
            }
            if let Some(s) = stroke_paint {
                items.push(PaintedPart { item: item(outline, None, Some(s), inh.opacity, even_odd), key: part.key.clone(), index: part.index });
            }
        } else {
            items.push(PaintedPart { item: item(path, fill_paint, stroke_paint, inh.opacity, even_odd), key: part.key.clone(), index: part.index });
        }
    }
    items
}

fn item(path: BezPath, fill: Option<Fill>, stroke: Option<Stroke>, opacity: f64, even_odd: bool) -> DrawItem {
    DrawItem { path, fill, stroke, opacity, clip: None, fill_rule_even_odd: even_odd, image: None, dots: None }
}
