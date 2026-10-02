//! Media queries for `k.Image` (natural size, decode check) and `k.SVG` (import).

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use kinemo_render::media::{import_svg, load_bitmap};

use crate::builder::Builder;

#[pymethods]
impl Builder {
    /// Pixel size `(width, height)` of a PNG/JPEG file; decodes it once (cached for render).
    fn image_size(&self, path: &str) -> PyResult<(u32, u32)> {
        let bitmap = load_bitmap(std::path::Path::new(path)).map_err(PyValueError::new_err)?;
        Ok((bitmap.width, bitmap.height))
    }

    /// The SVG document `data` as a JSON tree of groups and paths in scene units, scaled
    /// so its height is `height` and centered on the origin.
    fn svg_import(&self, data: &[u8], height: f64) -> PyResult<String> {
        let stroke_px_per_unit = 1080.0 / self.scene.config.frame_h;
        let tree = import_svg(data, height, stroke_px_per_unit).map_err(PyValueError::new_err)?;
        serde_json::to_string(&tree).map_err(|e| PyValueError::new_err(e.to_string()))
    }
}
