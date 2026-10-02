//! Glyph outlines: ttf-parser `OutlineBuilder` -> kurbo `BezPath`.

use kurbo::{BezPath, Point};
use rustybuzz::ttf_parser;

use crate::fonts::{fonts, scale};
use crate::types::FontStyle;

struct PathBuilder {
    path: BezPath,
    scale: f64,
    ox: f64,
    oy: f64,
}

impl PathBuilder {
    fn p(&self, x: f32, y: f32) -> Point {
        Point::new(x as f64 * self.scale + self.ox, y as f64 * self.scale + self.oy)
    }
}

impl ttf_parser::OutlineBuilder for PathBuilder {
    fn move_to(&mut self, x: f32, y: f32) {
        let p = self.p(x, y);
        self.path.move_to(p);
    }
    fn line_to(&mut self, x: f32, y: f32) {
        let p = self.p(x, y);
        self.path.line_to(p);
    }
    fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
        let (a, b) = (self.p(x1, y1), self.p(x, y));
        self.path.quad_to(a, b);
    }
    fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
        let (a, b, c) = (self.p(x1, y1), self.p(x2, y2), self.p(x, y));
        self.path.curve_to(a, b, c);
    }
    fn close(&mut self) {
        self.path.close_path();
    }
}

/// Outline of glyph `gid` of `style` at `size`, with its origin at `origin`
/// (scene units, y-up; font units are already y-up so nothing is flipped).
/// Returns an empty path for glyphs without an outline.
pub(crate) fn glyph_path(style: FontStyle, gid: u16, size: f64, origin: Point) -> BezPath {
    let face = fonts().get(style);
    let mut b = PathBuilder { path: BezPath::new(), scale: scale(face, size), ox: origin.x, oy: origin.y };
    face.outline_glyph(ttf_parser::GlyphId(gid), &mut b);
    b.path
}
