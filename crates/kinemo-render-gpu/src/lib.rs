//! Vello GPU backend for `kinemo-render`.
//!
//! [`VelloBackend`] implements [`kinemo_render::raster::RenderBackend`]: it encodes a
//! display list into a Vello scene, renders it headless to an `Rgba8Unorm` storage
//! texture with wgpu and reads the pixels back as straight-alpha RGBA8. The wgpu device,
//! the Vello renderer, the target texture and the readback buffers are created once and
//! reused across frames; [`RenderBackend::rasterize_batch`] encodes scenes in parallel
//! and submits every frame before waiting on any readback.
//!
//! The CPU backend (tiny-skia) stays the reference. GPU output differs by a few levels on
//! anti-aliased edges; [`image_difference`] measures it against [`GPU_TOLERANCE`].
//!
//! Without a usable adapter, [`VelloBackend::new`] returns an error; [`install`] registers
//! the backend with `kinemo_render::raster::backend`, which then falls back to the CPU.

mod gpu_context;
mod image_difference;
mod readback;
mod scene_encoding;
mod stroke_outline;
mod vello_backend;

pub use gpu_context::GpuBackendError;
pub use image_difference::{image_difference, ImageDifference, PixelTolerance, GPU_TOLERANCE};
pub use vello_backend::VelloBackend;

use kinemo_render::raster::{install_gpu_backend_factory, SharedRenderBackend};

fn create_shared_vello_backend() -> Result<SharedRenderBackend, String> {
    VelloBackend::new().map(|b| Box::new(b) as SharedRenderBackend).map_err(|e| e.to_string())
}

/// Makes `kinemo_render::raster::backend(BackendKind::GpuWithCpuFallback)` construct a
/// [`VelloBackend`]. Idempotent.
pub fn install() {
    install_gpu_backend_factory(create_shared_vello_backend);
}

/// A Vello backend if an adapter is available, else the CPU backend.
pub fn vello_or_cpu_backend() -> SharedRenderBackend {
    create_shared_vello_backend().unwrap_or_else(|_| Box::new(kinemo_render::raster::CpuBackend))
}
