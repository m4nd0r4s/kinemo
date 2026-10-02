//! Rasterization backends behind one interface.
//!
//! The CPU backend (tiny-skia) is the default and the reference for snapshot tests. A GPU
//! backend (Vello, crate `kinemo-render-gpu`) lives in its own crate so the default build
//! never pulls in wgpu; it plugs in through [`install_gpu_backend_factory`].

use std::sync::OnceLock;

use rayon::prelude::*;

use super::{rasterize, DisplayList, Image};

/// Turns a backend-neutral display list into a straight-alpha RGBA8 image.
pub trait RenderBackend {
    /// Rasterizes one frame. Items are drawn in order with source-over blending.
    fn rasterize(&self, display_list: &DisplayList, antialias: bool) -> Image;

    /// Rasterizes several frames; backends override this to pipeline work.
    fn rasterize_batch(&self, display_lists: &[DisplayList], antialias: bool) -> Vec<Image> {
        display_lists.iter().map(|dl| self.rasterize(dl, antialias)).collect()
    }

    /// Short identifier, e.g. `"cpu-tiny-skia"` or `"gpu-vello"`.
    fn name(&self) -> &'static str;
}

/// Which backend to construct with [`backend`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BackendKind {
    /// tiny-skia on the CPU: deterministic reference.
    Cpu,
    /// The installed GPU backend if one is installed and an adapter exists, else CPU.
    GpuWithCpuFallback,
}

/// The tiny-skia rasterizer.
#[derive(Clone, Copy, Debug, Default)]
pub struct CpuBackend;

impl RenderBackend for CpuBackend {
    fn rasterize(&self, display_list: &DisplayList, antialias: bool) -> Image {
        rasterize(display_list, antialias)
    }

    fn rasterize_batch(&self, display_lists: &[DisplayList], antialias: bool) -> Vec<Image> {
        display_lists.par_iter().map(|dl| rasterize(dl, antialias)).collect()
    }

    fn name(&self) -> &'static str {
        "cpu-tiny-skia"
    }
}

pub type SharedRenderBackend = Box<dyn RenderBackend + Send + Sync>;

/// Builds a GPU backend, or explains why none is available (e.g. no adapter).
pub type GpuBackendFactory = fn() -> Result<SharedRenderBackend, String>;

static GPU_BACKEND_FACTORY: OnceLock<GpuBackendFactory> = OnceLock::new();

/// Registers the GPU backend constructor (done by `kinemo_render_gpu::install`).
/// Returns `false` if a factory was already installed.
pub fn install_gpu_backend_factory(factory: GpuBackendFactory) -> bool {
    GPU_BACKEND_FACTORY.set(factory).is_ok()
}

/// Constructs a backend. `GpuWithCpuFallback` falls back to [`CpuBackend`] when no GPU
/// backend is installed or it fails to start (no adapter).
pub fn backend(kind: BackendKind) -> SharedRenderBackend {
    match kind {
        BackendKind::Cpu => Box::new(CpuBackend),
        BackendKind::GpuWithCpuFallback => GPU_BACKEND_FACTORY
            .get()
            .and_then(|factory| factory().ok())
            .unwrap_or_else(|| Box::new(CpuBackend)),
    }
}
