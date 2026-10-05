//! CPU rasterization of a display list with tiny-skia.

mod backend;
mod bitmap;
mod display_list;
mod paint;
mod png;

pub use backend::{backend, install_gpu_backend_factory, BackendKind, CpuBackend, GpuBackendFactory, RenderBackend, SharedRenderBackend};
pub use display_list::{Bitmap, Cap, DisplayList, DotCloud, DrawItem, Fill, Image, ImagePaint, Join, Stroke};
pub use paint::rasterize;
pub use png::encode_png;

#[cfg(test)]
mod tests;
