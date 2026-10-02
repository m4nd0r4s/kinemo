//! Media read from files: raster images (`k.Image`) and SVG illustrations (`k.SVG`).

mod bitmap_cache;
mod svg_import;

pub use bitmap_cache::{decode_bitmap, load_bitmap};
pub use svg_import::{import_svg, SvgImport, SvgNode, SvgNodeKind};

#[cfg(test)]
mod tests;
