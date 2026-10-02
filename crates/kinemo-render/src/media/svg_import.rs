//! SVG files → a tree of kinemo paths and groups (`k.SVG`), parsed with usvg.
//!
//! usvg resolves CSS, `<use>`, shapes and transforms; each path comes out with its
//! absolute transform baked in, converted to scene units (y-up), scaled so the drawing's
//! height is the requested height and centered on the origin. `<g>` elements stay
//! groups (so ids of groups and paths are addressable); gradients and patterns become
//! their mean color.

use kurbo::{BezPath, Point};
use serde::Serialize;
use usvg::tiny_skia_path::PathSegment;

/// The imported drawing.
#[derive(Clone, Debug, Serialize)]
pub struct SvgImport {
    /// Top-level nodes (the `<svg>` element itself is the kinemo `SVG` object).
    pub children: Vec<SvgNode>,
    /// Size of the drawing in scene units.
    pub width: f64,
    pub height: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct SvgNode {
    /// The element's `id`, when it has one.
    pub id: Option<String>,
    #[serde(flatten)]
    pub kind: SvgNodeKind,
}

#[derive(Clone, Debug, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SvgNodeKind {
    Group {
        opacity: f64,
        children: Vec<SvgNode>,
    },
    Path {
        /// Path data in scene units, y-up, transforms applied.
        d: String,
        /// Fill color (sRGB, alpha includes `fill-opacity`); `None` for `fill="none"`.
        fill: Option<[f64; 4]>,
        /// Stroke color (alpha includes `stroke-opacity`); `None` without a stroke.
        stroke: Option<[f64; 4]>,
        /// Stroke width in kinemo stroke units (pixels at 1080p).
        stroke_width: f64,
        even_odd: bool,
    },
}

/// Mapping from SVG user space (after transforms) into scene units.
struct Mapping {
    center: Point,
    units_per_svg: f64,
    stroke_px_per_unit: f64,
}

impl Mapping {
    fn point(&self, x: f32, y: f32) -> Point {
        Point::new((x as f64 - self.center.x) * self.units_per_svg, (self.center.y - y as f64) * self.units_per_svg)
    }
}

/// Parses SVG `data` and maps it so its height is `height` scene units, centered.
/// `stroke_px_per_unit` converts scene units into stroke-width units (1080 / frame height).
pub fn import_svg(data: &[u8], height: f64, stroke_px_per_unit: f64) -> Result<SvgImport, String> {
    let tree = usvg::Tree::from_data(data, &usvg::Options::default()).map_err(|e| e.to_string())?;
    let bounds = tree.root().abs_bounding_box();
    let (x, y, w, h) = if bounds.width() > 0.0 || bounds.height() > 0.0 {
        (bounds.x(), bounds.y(), bounds.width(), bounds.height())
    } else {
        (0.0, 0.0, tree.size().width(), tree.size().height())
    };
    let (w, h) = (w as f64, h as f64);
    let reference = if h > 1e-9 { h } else { w.max(1e-9) };
    let units_per_svg = height / reference;
    let mapping = Mapping {
        center: Point::new(x as f64 + w / 2.0, y as f64 + h / 2.0),
        units_per_svg,
        stroke_px_per_unit,
    };
    Ok(SvgImport {
        children: convert_children(tree.root(), &mapping),
        width: w * units_per_svg,
        height: h * units_per_svg,
    })
}

fn non_empty(id: &str) -> Option<String> {
    (!id.is_empty()).then(|| id.to_string())
}

fn convert_children(group: &usvg::Group, mapping: &Mapping) -> Vec<SvgNode> {
    group.children().iter().filter_map(|node| convert_node(node, mapping)).collect()
}

fn convert_group(group: &usvg::Group, id: Option<String>, mapping: &Mapping) -> Option<SvgNode> {
    let children = convert_children(group, mapping);
    if children.is_empty() && id.is_none() {
        return None;
    }
    let opacity = group.opacity().get() as f64;
    Some(SvgNode { id, kind: SvgNodeKind::Group { opacity, children } })
}

fn convert_node(node: &usvg::Node, mapping: &Mapping) -> Option<SvgNode> {
    match node {
        usvg::Node::Group(g) => convert_group(g, non_empty(g.id()), mapping),
        usvg::Node::Path(p) => convert_path(p, mapping),
        // Text is converted to outlines by usvg (when its fonts are available).
        usvg::Node::Text(t) => convert_group(t.flattened(), non_empty(t.id()), mapping),
        usvg::Node::Image(_) => None,
    }
}

fn convert_path(path: &usvg::Path, mapping: &Mapping) -> Option<SvgNode> {
    if !path.is_visible() {
        return None;
    }
    let ts = path.abs_transform();
    let map = |p: usvg::tiny_skia_path::Point| {
        let mut q = p;
        ts.map_point(&mut q);
        mapping.point(q.x, q.y)
    };
    let mut d = BezPath::new();
    for segment in path.data().segments() {
        match segment {
            PathSegment::MoveTo(p) => d.move_to(map(p)),
            PathSegment::LineTo(p) => d.line_to(map(p)),
            PathSegment::QuadTo(a, p) => d.quad_to(map(a), map(p)),
            PathSegment::CubicTo(a, b, p) => d.curve_to(map(a), map(b), map(p)),
            PathSegment::Close => d.close_path(),
        }
    }
    let fill = path.fill().map(|f| with_opacity(paint_color(f.paint()), f.opacity().get()));
    let even_odd = path.fill().is_some_and(|f| f.rule() == usvg::FillRule::EvenOdd);
    let (stroke, stroke_width) = match path.stroke() {
        Some(s) => {
            let transform_scale = ((ts.sx * ts.sy - ts.kx * ts.ky) as f64).abs().sqrt();
            let width = s.width().get() as f64 * transform_scale * mapping.units_per_svg * mapping.stroke_px_per_unit;
            (Some(with_opacity(paint_color(s.paint()), s.opacity().get())), width)
        }
        None => (None, 0.0),
    };
    if fill.is_none() && stroke.is_none() {
        return None;
    }
    Some(SvgNode {
        id: non_empty(path.id()),
        kind: SvgNodeKind::Path { d: d.to_svg(), fill, stroke, stroke_width, even_odd },
    })
}

fn rgb(c: usvg::Color) -> [f64; 3] {
    [c.red as f64 / 255.0, c.green as f64 / 255.0, c.blue as f64 / 255.0]
}

fn with_opacity(c: [f64; 4], opacity: f32) -> [f64; 4] {
    [c[0], c[1], c[2], (c[3] * opacity as f64).clamp(0.0, 1.0)]
}

/// Solid color of a paint; gradients use the mean of their stops.
fn paint_color(paint: &usvg::Paint) -> [f64; 4] {
    let stops = match paint {
        usvg::Paint::Color(c) => {
            let [r, g, b] = rgb(*c);
            return [r, g, b, 1.0];
        }
        usvg::Paint::LinearGradient(g) => g.stops(),
        usvg::Paint::RadialGradient(g) => g.stops(),
        usvg::Paint::Pattern(_) => return [0.5, 0.5, 0.5, 1.0],
    };
    if stops.is_empty() {
        return [0.0, 0.0, 0.0, 1.0];
    }
    let n = stops.len() as f64;
    let mut sum = [0.0; 4];
    for stop in stops {
        let [r, g, b] = rgb(stop.color());
        for (s, v) in sum.iter_mut().zip([r, g, b, stop.opacity().get() as f64]) {
            *s += v / n;
        }
    }
    sum
}
