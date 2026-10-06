//! Plain data types describing what to draw.

/// Solid fill. `color` is sRGB, straight alpha, components in 0..1.
#[derive(Clone, Debug)]
pub struct Fill {
    pub color: [f64; 4],
}

/// Stroke style. `width` and `dash` lengths are in pixels.
#[derive(Clone, Debug)]
pub struct Stroke {
    pub color: [f64; 4],
    pub width: f64,
    pub dash: Option<Vec<f64>>,
    pub cap: Cap,
    pub join: Join,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cap {
    Butt,
    Round,
    Square,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Join {
    Miter,
    Round,
    Bevel,
}

/// A decoded raster image, shared between frames (decoded once per file, see
/// [`crate::media::load_bitmap`]).
#[derive(Debug)]
pub struct Bitmap {
    pub width: u32,
    pub height: u32,
    /// Premultiplied-alpha RGBA8, row-major, `width * height * 4` bytes.
    pub premultiplied_rgba: Vec<u8>,
    /// Mean color (straight alpha), used where the image must act as a flat shape (morphs).
    pub average_color: [f64; 4],
    /// The original file bytes and their MIME type, embedded as-is by SVG export.
    pub encoded: Vec<u8>,
    pub mime: &'static str,
}

/// Paints a bitmap: `transform` maps image pixels (origin top-left, y-down) to output
/// pixels. Sampled with bilinear filtering.
#[derive(Clone, Debug)]
pub struct ImagePaint {
    pub bitmap: std::sync::Arc<Bitmap>,
    pub transform: kurbo::Affine,
}

/// One shape: fill is painted before stroke.
#[derive(Clone, Debug)]
pub struct DrawItem {
    /// Pixel coordinates, y-down.
    pub path: kurbo::BezPath,
    pub fill: Option<Fill>,
    pub stroke: Option<Stroke>,
    /// Multiplies both fill and stroke alpha.
    pub opacity: f64,
    /// Optional clip path in pixel coordinates (nonzero rule).
    pub clip: Option<kurbo::BezPath>,
    /// `false` = nonzero (required for text), `true` = even-odd.
    pub fill_rule_even_odd: bool,
    /// When set, the item paints this image (with `opacity` and `clip`) after fill and
    /// stroke; `path` is the image's outline in pixels (for morphs, picking and SVG).
    pub image: Option<ImagePaint>,
    /// When set, `path` is a union of small dots and the CPU rasterizer stamps them from
    /// these centers and radii instead of filling the path (thousands of dots fill much
    /// faster this way). Other consumers keep using `path`.
    pub dots: Option<DotCloud>,
    /// A soft halo painted under the item (see [`Glow`]).
    pub glow: Option<Glow>,
}

/// A blurred halo of an item's own shape, in its color: `radius` is the blur radius in pixels.
#[derive(Clone, Copy, Debug)]
pub struct Glow {
    pub color: [f64; 4],
    pub radius: f64,
}

/// Disks in pixel coordinates: the marks of a mass object, for fast stamping.
#[derive(Clone, Debug, Default)]
pub struct DotCloud {
    pub centers: Vec<[f32; 2]>,
    pub radii: Vec<f32>,
}

/// Straight-alpha RGBA8 image, row-major, `width * height * 4` bytes.
#[derive(Clone, Debug)]
pub struct Image {
    pub width: u32,
    pub height: u32,
    pub rgba: Vec<u8>,
}

#[derive(Clone, Debug, Default)]
pub struct DisplayList {
    pub width: u32,
    pub height: u32,
    /// sRGB straight alpha, 0..1.
    pub background: [f64; 4],
    pub items: Vec<DrawItem>,
}
