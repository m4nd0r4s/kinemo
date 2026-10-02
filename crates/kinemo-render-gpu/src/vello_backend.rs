//! The Vello implementation of `RenderBackend`.

use std::sync::Mutex;

use kinemo_render::raster::{DisplayList, Image, RenderBackend};
use rayon::prelude::*;
use vello::wgpu;

use crate::gpu_context::{GpuBackendError, GpuContext};
use crate::readback::RenderTargets;
use crate::scene_encoding::{convert_color, encode_display_list};

/// Frames submitted per readback wait in `rasterize_batch` (bounds buffer memory:
/// 16 × 1080p ≈ 133 MB).
const MAX_FRAMES_IN_FLIGHT: usize = 16;

struct RendererState {
    renderer: vello::Renderer,
    targets: Option<RenderTargets>,
}

/// Vello on wgpu, headless. One device, renderer and set of targets per backend,
/// serialized by a mutex (the GPU queue is serial anyway).
pub struct VelloBackend {
    context: GpuContext,
    state: Mutex<RendererState>,
}

impl VelloBackend {
    /// Creates the device and compiles Vello's shaders (area AA only).
    /// Fails when no adapter is available.
    pub fn new() -> Result<Self, GpuBackendError> {
        let context = GpuContext::new()?;
        let renderer = vello::Renderer::new(
            &context.device,
            vello::RendererOptions {
                antialiasing_support: vello::AaSupport::area_only(),
                ..Default::default()
            },
        )
        .map_err(|e| GpuBackendError::RendererCreationFailed(e.to_string()))?;
        Ok(VelloBackend { context, state: Mutex::new(RendererState { renderer, targets: None }) })
    }

    /// Adapter name and graphics API, e.g. `"Apple M2 (Metal)"`.
    pub fn adapter_description(&self) -> &str {
        &self.context.adapter_description
    }

    fn render_chunk(&self, display_lists: &[DisplayList]) -> Result<Vec<Image>, String> {
        let Some(first) = display_lists.first() else { return Ok(Vec::new()) };
        let (width, height) = (first.width, first.height);
        let scenes: Vec<vello::Scene> = display_lists.par_iter().map(encode_display_list).collect();
        let device = &self.context.device;
        let queue = &self.context.queue;
        let mut state = self.state.lock().map_err(|_| "renderer mutex poisoned".to_string())?;
        let RendererState { renderer, targets } = &mut *state;
        if targets.as_ref().is_none_or(|t| (t.width, t.height) != (width, height)) {
            *targets = Some(RenderTargets::new(device, width, height));
        }
        let targets = targets.as_mut().expect("targets were just created");
        targets.ensure_readback_buffers(device, scenes.len());
        for (slot, (scene, display_list)) in scenes.iter().zip(display_lists).enumerate() {
            let params = vello::RenderParams {
                base_color: convert_color(display_list.background, 1.0),
                width,
                height,
                antialiasing_method: vello::AaConfig::Area,
            };
            renderer.render_to_texture(device, queue, scene, &targets.view, &params).map_err(|e| e.to_string())?;
            let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("kinemo readback") });
            targets.encode_copy_to_buffer(&mut encoder, slot);
            queue.submit([encoder.finish()]);
        }
        let frames = targets.read_buffers(device, scenes.len())?;
        Ok(frames.into_iter().map(|rgba| Image { width, height, rgba }).collect())
    }

    /// Renders same-sized consecutive runs; empty sizes yield empty images like the CPU path.
    fn render_all(&self, display_lists: &[DisplayList]) -> Result<Vec<Image>, String> {
        let mut images = Vec::with_capacity(display_lists.len());
        let mut start = 0;
        while start < display_lists.len() {
            let size = (display_lists[start].width, display_lists[start].height);
            if size.0 == 0 || size.1 == 0 {
                images.push(Image { width: size.0, height: size.1, rgba: Vec::new() });
                start += 1;
                continue;
            }
            let run = display_lists[start..]
                .iter()
                .take(MAX_FRAMES_IN_FLIGHT)
                .take_while(|dl| (dl.width, dl.height) == size)
                .count();
            images.extend(self.render_chunk(&display_lists[start..start + run])?);
            start += run;
        }
        Ok(images)
    }
}

impl RenderBackend for VelloBackend {
    /// `antialias` is ignored: Vello always uses area anti-aliasing (the preview and the
    /// final render both request anti-aliasing).
    fn rasterize(&self, display_list: &DisplayList, antialias: bool) -> Image {
        self.rasterize_batch(std::slice::from_ref(display_list), antialias).pop().expect("one image per display list")
    }

    /// Falls back to tiny-skia for the batch if the GPU fails mid-flight (device lost).
    fn rasterize_batch(&self, display_lists: &[DisplayList], antialias: bool) -> Vec<Image> {
        self.render_all(display_lists).unwrap_or_else(|_| {
            display_lists.iter().map(|dl| kinemo_render::raster::rasterize(dl, antialias)).collect()
        })
    }

    fn name(&self) -> &'static str {
        "gpu-vello"
    }
}

const _: () = {
    const fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<VelloBackend>();
};
