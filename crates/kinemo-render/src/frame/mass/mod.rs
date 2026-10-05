//! Mass objects (`points`, `vector_field`, `stream_lines`) → draw items.
//!
//! Thousands of marks would make thousands of draw items through the generic style
//! path; instead marks are merged into one path per quantized color ([`Buckets`]), so a
//! frame of 10k dots in a gradient costs a few hundred fills. The style chain still
//! applies: inherited opacity (`opacity`, fades) and tint, and the `_draw` / `_write`
//! progress of `k.draw` (reveal order: point index, arrow growth, line growth).

mod field;
mod points;

use std::collections::BTreeMap;

use kurbo::{Affine, BezPath};

use kinemo_eval::color;
use kinemo_ir::ObjectId;
use kinemo_layout::Layout;

use super::style::{chain_min, inherited};
use super::FrameSize;
use crate::raster::{Cap, DotCloud, DrawItem, Fill, Join, Stroke};

/// What every mass painter receives.
pub(super) struct MassContext<'l, 'a> {
    pub layout: &'l Layout<'a>,
    pub leaf: ObjectId,
    pub t: f64,
    /// Local → pixels.
    pub to_px: Affine,
    /// Stroke widths: 1080p pixels → output pixels.
    pub stroke_scale: f64,
    /// Reveal progress in `[0, 1]` (`k.draw`).
    pub progress: f64,
    tint: Option<([f64; 4], f64)>,
}

impl MassContext<'_, '_> {
    /// A mark's color after the inherited tint.
    pub fn tinted(&self, c: [f64; 4]) -> [f64; 4] {
        match self.tint {
            Some((tc, a)) => color::mix(c, [tc[0], tc[1], tc[2], c[3]], a),
            None => c,
        }
    }
}

pub(crate) fn draw_items(layout: &Layout, leaf: ObjectId, t: f64, size: FrameSize) -> Vec<DrawItem> {
    let inh = inherited(layout, leaf, t);
    let progress = chain_min(layout, leaf, "_draw", t).min(chain_min(layout, leaf, "_write", t)).clamp(0.0, 1.0);
    if inh.opacity <= 0.0 || progress <= 0.0 {
        return vec![];
    }
    let cx = MassContext {
        layout,
        leaf,
        t,
        to_px: size.pixel_affine(layout.scene()) * layout.render_affine(leaf, t),
        stroke_scale: size.stroke_scale(),
        progress,
        tint: inh.tint,
    };
    let mut items = match layout.scene().object(leaf).kind.as_str() {
        "points" => points::draw(&cx),
        "vector_field" => field::arrows(&cx),
        "stream_lines" => field::lines(&cx),
        _ => vec![],
    };
    for item in &mut items {
        item.opacity *= inh.opacity;
    }
    items
}

/// Color quantized to 8 bits per channel (bucket key).
type ColorKey = [u8; 4];

fn color_key(c: [f64; 4]) -> ColorKey {
    c.map(|v| (v.clamp(0.0, 1.0) * 255.0).round() as u8)
}

/// Marks merged into one path per (quantized color, layer). Iteration is ordered by
/// layer then color, so output is deterministic.
#[derive(Default)]
pub(super) struct Buckets {
    paths: BTreeMap<(u32, ColorKey), Bucket>,
}

struct Bucket {
    color: [f64; 4],
    path: BezPath,
    /// The same marks as disks, while every mark of the bucket is one (see `DrawItem::dots`).
    dots: Option<DotCloud>,
}

impl Buckets {
    fn bucket(&mut self, layer: u32, color: [f64; 4]) -> &mut Bucket {
        self.paths.entry((layer, color_key(color))).or_insert_with(|| Bucket { color, path: BezPath::new(), dots: Some(DotCloud::default()) })
    }

    /// The path collecting marks of `color` in `layer` (lower layers draw first).
    pub fn path(&mut self, layer: u32, color: [f64; 4]) -> &mut BezPath {
        let bucket = self.bucket(layer, color);
        // A mark that is not a disk: the bucket fills its path.
        bucket.dots = None;
        &mut bucket.path
    }

    /// The path collecting disks of `color` in `layer`, and the disk itself (pixels), so the
    /// rasterizer can stamp the bucket instead of filling its path.
    pub fn disk(&mut self, layer: u32, color: [f64; 4], center_px: kurbo::Point, radius_px: f64) -> &mut BezPath {
        let bucket = self.bucket(layer, color);
        if let Some(dots) = &mut bucket.dots {
            dots.centers.push([center_px.x as f32, center_px.y as f32]);
            dots.radii.push(radius_px as f32);
        }
        &mut bucket.path
    }

    pub fn into_fills(self) -> Vec<DrawItem> {
        self.paths
            .into_values()
            .filter(|bucket| !bucket.path.elements().is_empty())
            .map(|Bucket { color, path, dots }| DrawItem {
                path,
                fill: Some(Fill { color }),
                stroke: None,
                opacity: 1.0,
                clip: None,
                fill_rule_even_odd: false,
                image: None,
                dots: dots.filter(|dots| !dots.centers.is_empty()),
            })
            .collect()
    }

    pub fn into_strokes(self, width: f64, cap: Cap) -> Vec<DrawItem> {
        self.paths
            .into_values()
            .filter(|bucket| !bucket.path.elements().is_empty())
            .map(|Bucket { color, path, .. }| DrawItem {
                path,
                fill: None,
                stroke: Some(Stroke { color, width, dash: None, cap, join: Join::Round }),
                opacity: 1.0,
                clip: None,
                fill_rule_even_odd: false,
                image: None,
                dots: None,
            })
            .collect()
    }
}

#[cfg(test)]
mod tests;
