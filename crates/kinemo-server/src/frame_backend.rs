//! The rasterization backend for preview frames, chosen once per process.
//!
//! Built with feature `gpu`, the preview uses Vello when a GPU adapter is available and
//! falls back to tiny-skia otherwise; without it, always tiny-skia. Set
//! `KINEMO_PREVIEW_BACKEND=cpu` to force the CPU even in a GPU build.

use std::sync::OnceLock;

use kinemo_render::raster::{CpuBackend, RenderBackend, SharedRenderBackend};

fn choose_backend() -> SharedRenderBackend {
    if std::env::var("KINEMO_PREVIEW_BACKEND").is_ok_and(|v| v.eq_ignore_ascii_case("cpu")) {
        return Box::new(CpuBackend);
    }
    #[cfg(feature = "gpu")]
    {
        kinemo_render_gpu::vello_or_cpu_backend()
    }
    #[cfg(not(feature = "gpu"))]
    {
        Box::new(CpuBackend)
    }
}

/// Shared backend; the GPU device and Vello shaders are created on first use.
pub fn preview_frame_backend() -> &'static dyn RenderBackend {
    static BACKEND: OnceLock<SharedRenderBackend> = OnceLock::new();
    BACKEND.get_or_init(choose_backend).as_ref()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backend_matches_the_build_features() {
        let name = preview_frame_backend().name();
        if cfg!(feature = "gpu") {
            assert!(["gpu-vello", "cpu-tiny-skia"].contains(&name), "{name}");
        } else {
            assert_eq!(name, "cpu-tiny-skia");
        }
    }
}
