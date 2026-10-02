//! GPU (Vello) vs CPU (tiny-skia reference) per-pixel tolerance tests.
//! Each test prints its measured difference; all skip when no GPU adapter is available.

mod support;

use kinemo_render::raster::{backend, rasterize, BackendKind, DisplayList, RenderBackend};
use kinemo_render::{display_list, FrameSize};
use kinemo_render_gpu::{image_difference, ImageDifference, GPU_TOLERANCE};

fn compare(name: &str, dl: &DisplayList) -> Option<ImageDifference> {
    let gpu = support::gpu_backend()?;
    let reference = rasterize(dl, true);
    let candidate = gpu.rasterize(dl, true);
    let diff = image_difference(&reference, &candidate, &GPU_TOLERANCE);
    eprintln!(
        "{name}: max channel diff {}, outside 3x3 neighborhood {}, {:.3}% pixels > {}, mean abs diff {:.3}",
        diff.max_channel_difference,
        diff.max_neighborhood_difference,
        diff.fraction_of_differing_pixels() * 100.0,
        GPU_TOLERANCE.differing_pixel_threshold,
        diff.mean_absolute_difference
    );
    Some(diff)
}

fn assert_within_tolerance(name: &str, dl: &DisplayList) {
    if let Some(diff) = compare(name, dl) {
        assert!(diff.is_within(&GPU_TOLERANCE), "{name} exceeds GPU tolerance {GPU_TOLERANCE:?}: {diff:?}");
    }
}

#[test]
fn shapes_match_reference() {
    assert_within_tolerance("shapes", &support::shapes_scene());
}

#[test]
fn strokes_with_dashes_match_reference() {
    assert_within_tolerance("strokes_with_dashes", &support::strokes_scene());
}

#[test]
fn text_glyphs_match_reference() {
    assert_within_tolerance("text_glyphs", &support::text_scene());
}

#[test]
fn opacity_matches_reference() {
    assert_within_tolerance("opacity", &support::opacity_scene());
}

#[test]
fn transparent_background_is_straight_alpha() {
    assert_within_tolerance("transparent_background", &support::transparent_background_scene());
}

#[test]
fn clips_match_reference() {
    assert_within_tolerance("clips", &support::clip_scene());
}

#[test]
fn even_odd_fill_rule_matches_reference() {
    assert_within_tolerance("even_odd", &support::even_odd_scene());
}

fn bubble_sort_scene() -> kinemo_ir::Scene {
    let json = include_str!("fixtures/bubble_sort_scene.json");
    kinemo_ir::Scene::from_json(json).expect("bubble sort fixture parses (regenerate it if the IR changed)")
}

#[test]
fn bubble_sort_frames_at_1080p_match_reference() {
    if support::gpu_backend().is_none() {
        return;
    }
    let scene = bubble_sort_scene();
    let size = FrameSize { width: 1920, height: 1080 };
    for t in [0.4, 2.0, 6.0, 11.0] {
        assert_within_tolerance(&format!("bubble_sort@{t}s"), &display_list(&scene, t, size, false));
    }
}

#[test]
fn batch_rendering_matches_single_frames() {
    let Some(gpu) = support::gpu_backend() else { return };
    let named = support::all_scenes();
    let scenes: Vec<DisplayList> = named.iter().map(|(_, dl)| dl.clone()).collect();
    let batch = gpu.rasterize_batch(&scenes, true);
    for ((name, dl), batched) in named.iter().zip(&batch) {
        let single = gpu.rasterize(dl, true);
        let differing = single.rgba.iter().zip(&batched.rgba).filter(|(a, b)| a != b).count();
        assert_eq!(differing, 0, "{name}: batched frame differs from single-frame render in {differing} bytes");
    }
}

#[test]
fn empty_frame_size_yields_empty_image() {
    let Some(gpu) = support::gpu_backend() else { return };
    let image = gpu.rasterize(&DisplayList::default(), true);
    assert!(image.rgba.is_empty());
}

#[test]
fn installed_factory_is_used_with_cpu_fallback() {
    kinemo_render_gpu::install();
    let chosen = backend(BackendKind::GpuWithCpuFallback);
    let expected = if support::gpu_backend().is_some() { "gpu-vello" } else { "cpu-tiny-skia" };
    assert_eq!(chosen.name(), expected);
    assert_eq!(backend(BackendKind::Cpu).name(), "cpu-tiny-skia");
}

/// Why the tolerance is anti-aliasing aware: against an 8×8 supersampled ground truth,
/// Vello's edges are at least as accurate as tiny-skia's, so CPU-vs-GPU edge differences
/// are mostly the reference's own coverage error. (Means are printed, not asserted:
/// translucent interiors differ by ±1 level from rounding, f32 on the GPU vs tiny-skia's
/// 8-bit pipeline, which raises the GPU mean without being an edge error.)
#[test]
fn gpu_edges_are_at_least_as_close_to_supersampled_truth_as_cpu() {
    let Some(gpu) = support::gpu_backend() else { return };
    for (name, dl) in support::all_scenes() {
        let truth = support::supersampled_reference(&dl, 8);
        let cpu_error = image_difference(&truth, &rasterize(&dl, true), &GPU_TOLERANCE);
        let gpu_error = image_difference(&truth, &gpu.rasterize(&dl, true), &GPU_TOLERANCE);
        eprintln!(
            "{name}: vs 8x8 truth — CPU max {} mean {:.3}, GPU max {} mean {:.3}",
            cpu_error.max_channel_difference,
            cpu_error.mean_absolute_difference,
            gpu_error.max_channel_difference,
            gpu_error.mean_absolute_difference
        );
        assert!(gpu_error.max_channel_difference <= cpu_error.max_channel_difference, "{name}");
    }
}
