//! Frame walking: typst frame items → glyph and rule paths in scene units,
//! each attributed to the part-tree node identified by its marker color.

use kurbo::{Affine, BezPath, Rect};
use typst::layout::{Frame, FrameItem, Transform};
use typst::visualize::Paint;

use crate::convert::{node_of_rgb, DOCUMENT_FONT_PT};
use crate::outline::{geometry_path, glyph_outline, pt, stroke_outline};
use crate::types::MathGlyph;

/// Ink of a laid-out formula.
pub(crate) struct FrameInk {
    pub(crate) glyphs: Vec<MathGlyph>,
    /// Per glyph: whether it is a prime (′ ″ ‴ ⁗).
    pub(crate) is_prime: Vec<bool>,
    pub(crate) rules: Vec<(BezPath, usize)>,
    pub(crate) bbox: Rect,
}

/// Collect the ink of `frame` scaled so that 1 em = `size` scene units, y-up,
/// with the frame's box centered at the origin. Marker colors that do not name
/// one of `node_count` nodes map to the root.
pub(crate) fn collect(frame: &Frame, size: f64, node_count: usize) -> FrameInk {
    let k = size / DOCUMENT_FONT_PT;
    let (w, h) = (pt(frame.width()), pt(frame.height()));
    let scene = Affine::new([k, 0.0, 0.0, -k, -w / 2.0 * k, h / 2.0 * k]);
    let mut walker = Walker { node_count, glyphs: Vec::new(), is_prime: Vec::new(), rules: Vec::new() };
    walker.frame(frame, scene);
    FrameInk {
        glyphs: walker.glyphs,
        is_prime: walker.is_prime,
        rules: walker.rules,
        bbox: Rect::new(-w / 2.0 * k, -h / 2.0 * k, w / 2.0 * k, h / 2.0 * k),
    }
}

fn affine_of(t: &Transform) -> Affine {
    Affine::new([t.sx.get(), t.ky.get(), t.kx.get(), t.sy.get(), pt(t.tx), pt(t.ty)])
}

struct Walker {
    node_count: usize,
    glyphs: Vec<MathGlyph>,
    is_prime: Vec<bool>,
    rules: Vec<(BezPath, usize)>,
}

impl Walker {
    fn node_of(&self, paint: &Paint) -> usize {
        let Paint::Solid(color) = paint else { return 0 };
        let [r, g, b, _] = color.to_vec4_u8();
        let node = node_of_rgb([r, g, b]);
        if node < self.node_count {
            node
        } else {
            0
        }
    }

    /// `transform` maps `frame`'s coordinates (pt, y-down) to scene units.
    fn frame(&mut self, frame: &Frame, transform: Affine) {
        for (pos, item) in frame.items() {
            let at = transform * Affine::translate((pt(pos.x), pt(pos.y)));
            match item {
                FrameItem::Group(group) => self.frame(&group.frame, at * affine_of(&group.transform)),
                FrameItem::Text(text) => {
                    let node = self.node_of(&text.fill);
                    let font = &text.font;
                    let face = font.ttf();
                    let size = pt(text.size);
                    let scale = size / font.units_per_em();
                    let (mut x, mut y) = (0.0, 0.0);
                    for glyph in &text.glyphs {
                        let ox = x + glyph.x_offset.get() * size;
                        let oy = y + glyph.y_offset.get() * size;
                        if let Some(mut path) = glyph_outline(face, glyph.id) {
                            path.apply_affine(at * Affine::new([scale, 0.0, 0.0, -scale, ox, -oy]));
                            self.glyphs.push(MathGlyph { path, node });
                            let text = &text.text[glyph.range()];
                            self.is_prime.push(text.chars().all(|c| matches!(c, '′' | '″' | '‴' | '⁗')));
                        }
                        x += glyph.x_advance.get() * size;
                        y += glyph.y_advance.get() * size;
                    }
                }
                FrameItem::Shape(shape, _) => {
                    let path = geometry_path(&shape.geometry);
                    if let Some(fill) = &shape.fill {
                        let mut filled = path.clone();
                        filled.apply_affine(at);
                        self.rules.push((filled, self.node_of(fill)));
                    }
                    if let Some(stroke) = &shape.stroke {
                        self.rules.push((stroke_outline(&path, stroke, at), self.node_of(&stroke.paint)));
                    }
                }
                FrameItem::Image(..) | FrameItem::Link(..) | FrameItem::Tag(_) => {}
            }
        }
    }
}
