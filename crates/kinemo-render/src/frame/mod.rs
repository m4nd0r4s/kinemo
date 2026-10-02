//! Builds the display list of one frame: what to draw, where, and with which style.

pub(crate) mod collect;
mod image;
mod mass;
mod morph;
mod reveal;
pub(crate) mod style;

use kurbo::Affine;

use kinemo_eval::Evaluator;
use kinemo_ir::Scene;
use kinemo_layout::Layout;

use crate::raster::DisplayList;

/// Output size in pixels. The scene frame (in units) is scaled to fit the width.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FrameSize {
    pub width: u32,
    pub height: u32,
}

impl FrameSize {
    /// Pixels per scene unit.
    pub fn scale(&self, scene: &Scene) -> f64 {
        self.width as f64 / scene.config.frame_w
    }

    /// Scene units (y-up, origin at center) → pixels (y-down, origin top-left).
    pub fn pixel_affine(&self, scene: &Scene) -> Affine {
        let s = self.scale(scene);
        let (fw, fh) = (scene.config.frame_w, scene.config.frame_h);
        Affine::new([s, 0.0, 0.0, -s, fw / 2.0 * s, fh / 2.0 * s])
    }

    /// Stroke widths are given in pixels at 1080p; this converts them to output pixels.
    pub fn stroke_scale(&self) -> f64 {
        self.height as f64 / 1080.0
    }
}

/// Display list of `scene` at time `t`.
pub fn display_list(scene: &Scene, t: f64, size: FrameSize, transparent: bool) -> DisplayList {
    let ev = Evaluator::new(scene);
    let layout = Layout::new(&ev);
    let mut background = scene.config.background;
    if transparent {
        background[3] = 0.0;
    }
    let items = collect::leaves(&layout, t)
        .into_iter()
        .flat_map(|leaf| match layout.scene().object(leaf).kind.as_str() {
            "morph" => morph::draw_items(&layout, leaf, t, size),
            k if kinemo_layout::mass::is_mass_kind(k) => mass::draw_items(&layout, leaf, t, size),
            _ => style::draw_items(&layout, leaf, t, size),
        })
        .collect();
    DisplayList { width: size.width, height: size.height, background, items }
}

/// A part of a subtree as a morph sees it (Python pairs parts; the renderer interpolates).
#[derive(Clone, Debug, serde::Serialize)]
pub struct MorphPart {
    pub key: Option<String>,
    /// Center in scene units.
    pub center: [f64; 2],
    /// Leaf the part belongs to and its glyph index in that leaf's text-like source.
    pub leaf: kinemo_ir::ObjectId,
    pub index: usize,
}

/// Parts of a subtree in draw order.
pub fn morph_parts(scene: &Scene, root: kinemo_ir::ObjectId, t: f64) -> Vec<MorphPart> {
    let ev = Evaluator::new(scene);
    let layout = Layout::new(&ev);
    let size = FrameSize { width: scene.config.width, height: scene.config.height };
    let to_units = size.pixel_affine(scene).inverse();
    morph::subtree_parts(&layout, root, t, size)
        .into_iter()
        .map(|(leaf, part)| {
            let c = to_units * kurbo::Shape::bounding_box(&part.item.path).center();
            MorphPart { key: part.key, center: [c.x, c.y], leaf, index: part.index }
        })
        .collect()
}
