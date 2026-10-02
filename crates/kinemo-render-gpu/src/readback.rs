//! Render target texture and pooled readback buffers, reused while the size is unchanged.

use rayon::prelude::*;
use vello::wgpu;

/// wgpu requires `bytes_per_row` in texture→buffer copies to be a multiple of 256.
fn padded_bytes_per_row(width: u32) -> u32 {
    let unpadded = width * 4;
    let align = wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    unpadded.div_ceil(align) * align
}

/// Vello un-premultiplies with a tiny epsilon, so alpha-0 pixels can carry arbitrary
/// color; tiny-skia stores them as 0,0,0,0.
fn clear_color_of_transparent_pixels(rgba: &mut [u8]) {
    for px in rgba.chunks_exact_mut(4) {
        if px[3] == 0 {
            px.copy_from_slice(&[0, 0, 0, 0]);
        }
    }
}

pub(crate) struct RenderTargets {
    pub width: u32,
    pub height: u32,
    pub texture: wgpu::Texture,
    pub view: wgpu::TextureView,
    readback_buffers: Vec<wgpu::Buffer>,
}

impl RenderTargets {
    pub fn new(device: &wgpu::Device, width: u32, height: u32) -> Self {
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("kinemo vello target"),
            size: wgpu::Extent3d { width, height, depth_or_array_layers: 1 },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::STORAGE_BINDING | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        RenderTargets { width, height, texture, view, readback_buffers: Vec::new() }
    }

    /// Grows the buffer pool so that `count` frames can be in flight at once.
    pub fn ensure_readback_buffers(&mut self, device: &wgpu::Device, count: usize) {
        let size = padded_bytes_per_row(self.width) as u64 * self.height as u64;
        while self.readback_buffers.len() < count {
            self.readback_buffers.push(device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("kinemo vello readback"),
                size,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            }));
        }
    }

    /// Records a copy of the target texture into readback buffer `slot`.
    pub fn encode_copy_to_buffer(&self, encoder: &mut wgpu::CommandEncoder, slot: usize) {
        encoder.copy_texture_to_buffer(
            wgpu::TexelCopyTextureInfo {
                texture: &self.texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            wgpu::TexelCopyBufferInfo {
                buffer: &self.readback_buffers[slot],
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(padded_bytes_per_row(self.width)),
                    rows_per_image: Some(self.height),
                },
            },
            wgpu::Extent3d { width: self.width, height: self.height, depth_or_array_layers: 1 },
        );
    }

    /// Maps buffers `0..count`, waits once for the GPU, and returns tightly packed RGBA8.
    /// Vello's fine stage stores un-premultiplied (straight-alpha) colors.
    pub fn read_buffers(&self, device: &wgpu::Device, count: usize) -> Result<Vec<Vec<u8>>, String> {
        let receivers: Vec<_> = self.readback_buffers[..count]
            .iter()
            .map(|buffer| {
                let (sender, receiver) = std::sync::mpsc::channel();
                buffer.slice(..).map_async(wgpu::MapMode::Read, move |result| {
                    let _ = sender.send(result);
                });
                receiver
            })
            .collect();
        device.poll(wgpu::PollType::wait_indefinitely()).map_err(|e| e.to_string())?;
        let row_bytes = (self.width * 4) as usize;
        let padded = padded_bytes_per_row(self.width) as usize;
        let mut frames = Vec::with_capacity(count);
        for (buffer, receiver) in self.readback_buffers[..count].iter().zip(receivers) {
            receiver.recv().map_err(|e| e.to_string())?.map_err(|e| e.to_string())?;
            let mapped = buffer.slice(..).get_mapped_range();
            let source: &[u8] = &mapped;
            let mut rgba = vec![0u8; row_bytes * self.height as usize];
            // Parallel rows: the copy out of the mapped buffer is page-fault bound.
            rgba.par_chunks_mut(row_bytes).zip(source.par_chunks(padded)).for_each(|(row, padded_row)| {
                row.copy_from_slice(&padded_row[..row_bytes]);
                clear_color_of_transparent_pixels(row);
            });
            drop(mapped);
            buffer.unmap();
            frames.push(rgba);
        }
        Ok(frames)
    }
}
