//! CPU (tiny-skia) vs GPU (Vello) rasterization of the bubble sort scene at 1080p.
//!
//! cargo run --release -p kinemo-render-gpu --example benchmark_1080p [-- <frame count>]
//!
//! Display lists are built once up front (identical input for both backends); only
//! rasterization + readback is timed. Reported modes:
//! - per frame, one at a time (the preview's request/response path);
//! - batch throughput (the final render: CPU uses all cores via rayon, GPU pipelines
//!   up to 16 frames per readback wait).

use std::time::{Duration, Instant};

use kinemo_render::raster::{Cap, CpuBackend, DisplayList, DrawItem, Fill, Join, Stroke};
use kinemo_render::raster::RenderBackend;
use kurbo::{Affine, Circle, Shape};
use kinemo_render::{display_list, FrameSize};
use kinemo_render_gpu::{image_difference, VelloBackend, GPU_TOLERANCE};

fn milliseconds_per_frame(elapsed: Duration, frames: usize) -> f64 {
    elapsed.as_secs_f64() * 1000.0 / frames as f64
}

fn time_one_at_a_time(backend: &dyn RenderBackend, lists: &[DisplayList]) -> f64 {
    let start = Instant::now();
    for dl in lists {
        std::hint::black_box(backend.rasterize(dl, true));
    }
    milliseconds_per_frame(start.elapsed(), lists.len())
}

fn time_batched(backend: &dyn RenderBackend, lists: &[DisplayList]) -> f64 {
    let start = Instant::now();
    for chunk in lists.chunks(32) {
        std::hint::black_box(backend.rasterize_batch(chunk, true));
    }
    milliseconds_per_frame(start.elapsed(), lists.len())
}

/// A text- and shape-heavy 1080p frame (≈ 1,500 glyphs, 400 stroked circles), varied
/// per frame so nothing is cached: shows how the backends scale with scene complexity.
fn dense_display_list(frame: usize) -> DisplayList {
    let mut items = Vec::new();
    let options = kinemo_text::TextOptions { size: 0.3, ..Default::default() };
    let line = kinemo_text::layout("The quick brown fox jumps over the lazy dog: O(n log n) `sort()` 0123456789", &options);
    for row in 0..24 {
        let to_pixels = Affine::new([60.0, 0.0, 0.0, -60.0, 960.0 + (frame % 7) as f64, 40.0 + row as f64 * 42.0]);
        for glyph in &line.glyphs {
            items.push(DrawItem {
                path: to_pixels * glyph.path.clone(),
                fill: Some(Fill { color: [0.9, 0.9, 0.92, 1.0] }),
                stroke: None,
                opacity: 1.0,
                clip: None,
                fill_rule_even_odd: false,
                image: None,
                dots: None, glow: None,
            });
        }
    }
    for i in 0..400 {
        let center = ((i % 40) as f64 * 48.0 + 24.0, (i / 40) as f64 * 100.0 + 50.0 + frame as f64 * 0.37);
        items.push(DrawItem {
            path: Circle::new(center, 18.0).to_path(0.1),
            fill: Some(Fill { color: [0.2, 0.5, 0.9, 0.6] }),
            stroke: Some(Stroke { color: [1.0, 0.8, 0.2, 1.0], width: 2.5, dash: (i % 3 == 0).then(|| vec![6.0, 4.0]), cap: Cap::Round, join: Join::Round }),
            opacity: 0.9,
            clip: None,
            fill_rule_even_odd: false,
            image: None,
            dots: None, glow: None,
        });
    }
    DisplayList { width: 1920, height: 1080, background: [0.078, 0.082, 0.102, 1.0], items }
}

fn report(label: &str, gpu: &VelloBackend, lists: &[DisplayList]) {
    let items: usize = lists.iter().map(|dl| dl.items.len()).sum();
    let (width, height) = (lists[0].width, lists[0].height);
    println!("\n{label}: {width}x{height}, {} frames, {:.0} draw items/frame", lists.len(), items as f64 / lists.len() as f64);
    // Warm up both (shader pipelines, allocations).
    gpu.rasterize_batch(&lists[..lists.len().min(16)], true);
    CpuBackend.rasterize_batch(&lists[..lists.len().min(16)], true);
    let worst = lists
        .iter()
        .step_by((lists.len() / 12).max(1))
        .map(|dl| image_difference(&CpuBackend.rasterize(dl, true), &gpu.rasterize(dl, true), &GPU_TOLERANCE))
        .max_by(|a, b| a.fraction_of_differing_pixels().total_cmp(&b.fraction_of_differing_pixels()))
        .expect("at least one frame");
    println!(
        "  tolerance (worst sampled frame): max channel diff {}, outside 3x3 neighborhood {}, {:.3}% pixels > {}, within: {}",
        worst.max_channel_difference,
        worst.max_neighborhood_difference,
        worst.fraction_of_differing_pixels() * 100.0,
        GPU_TOLERANCE.differing_pixel_threshold,
        worst.is_within(&GPU_TOLERANCE)
    );
    let cpu_single = time_one_at_a_time(&CpuBackend, lists);
    let gpu_single = time_one_at_a_time(gpu, lists);
    let cpu_batch = time_batched(&CpuBackend, lists);
    let gpu_batch = time_batched(gpu, lists);
    println!("  one frame at a time (preview): CPU {cpu_single:7.2} ms   GPU {gpu_single:7.2} ms   GPU speedup {:.2}x", cpu_single / gpu_single);
    println!(
        "  batched (final render, CPU on {} threads): CPU {cpu_batch:7.2} ms   GPU {gpu_batch:7.2} ms   GPU speedup {:.2}x",
        rayon::current_num_threads(),
        cpu_batch / gpu_batch
    );
}

fn main() {
    let frame_count: usize = std::env::args().nth(1).and_then(|a| a.parse().ok()).unwrap_or(240);
    let json = include_str!("../tests/fixtures/bubble_sort_scene.json");
    let scene = kinemo_ir::Scene::from_json(json).expect("fixture parses");
    let size = FrameSize { width: 1920, height: 1080 };
    let lists: Vec<DisplayList> = (0..frame_count)
        .map(|i| display_list(&scene, scene.duration * i as f64 / frame_count as f64, size, false))
        .collect();
    let gpu = match VelloBackend::new() {
        Ok(gpu) => gpu,
        Err(e) => {
            println!("no GPU backend ({e}); CPU only: {:.2} ms/frame", time_one_at_a_time(&CpuBackend, &lists));
            return;
        }
    };
    println!("GPU adapter: {}", gpu.adapter_description());
    report("bubble sort scene", &gpu, &lists);
    let draft = FrameSize { width: 960, height: 540 };
    let draft_lists: Vec<DisplayList> = (0..frame_count)
        .map(|i| display_list(&scene, scene.duration * i as f64 / frame_count as f64, draft, false))
        .collect();
    report("bubble sort scene at the preview's draft size", &gpu, &draft_lists);
    let dense: Vec<DisplayList> = (0..frame_count.min(60)).map(dense_display_list).collect();
    report("dense synthetic frame", &gpu, &dense);
}
