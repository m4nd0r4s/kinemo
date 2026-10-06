//! Shared helpers: a lazily created GPU backend and display-list builders.

#![allow(dead_code)]

use std::sync::OnceLock;

use kinemo_render::raster::{Cap, DisplayList, DrawItem, Fill, Join, Stroke};
use kinemo_render_gpu::VelloBackend;
use kurbo::{Affine, BezPath, Circle, Rect, RoundedRect, Shape};

/// One backend for the whole test binary (shader compilation is the expensive part).
/// `None` (and a note on stderr) when no adapter is available: tests then skip.
pub fn gpu_backend() -> Option<&'static VelloBackend> {
    static BACKEND: OnceLock<Option<VelloBackend>> = OnceLock::new();
    BACKEND
        .get_or_init(|| match VelloBackend::new() {
            Ok(backend) => {
                eprintln!("GPU adapter: {}", backend.adapter_description());
                Some(backend)
            }
            Err(e) => {
                eprintln!("skipping GPU tests: {e}");
                None
            }
        })
        .as_ref()
}

pub const DARK_BACKGROUND: [f64; 4] = [0.078, 0.082, 0.102, 1.0];

pub fn display_list(width: u32, height: u32, items: Vec<DrawItem>) -> DisplayList {
    DisplayList { width, height, background: DARK_BACKGROUND, items }
}

pub fn filled(path: BezPath, color: [f64; 4]) -> DrawItem {
    DrawItem { path, fill: Some(Fill { color }), stroke: None, opacity: 1.0, clip: None, fill_rule_even_odd: false, image: None, dots: None, glow: None }
}

pub fn stroked(path: BezPath, color: [f64; 4], width: f64, dash: Option<Vec<f64>>, cap: Cap, join: Join) -> DrawItem {
    DrawItem {
        path,
        fill: None,
        stroke: Some(Stroke { color, width, dash, cap, join }),
        opacity: 1.0,
        clip: None,
        fill_rule_even_odd: false,
        image: None,
        dots: None, glow: None,
    }
}

pub fn shapes_scene() -> DisplayList {
    display_list(
        320,
        200,
        vec![
            filled(Rect::new(20.0, 20.0, 120.0, 90.0).to_path(0.1), [0.9, 0.2, 0.2, 1.0]),
            filled(Circle::new((200.0, 70.0), 45.0).to_path(0.1), [0.2, 0.6, 0.95, 1.0]),
            filled(RoundedRect::new(40.0, 110.0, 290.0, 180.0, 18.0).to_path(0.1), [0.95, 0.8, 0.2, 1.0]),
            filled(triangle((150.0, 100.0), (300.0, 190.0), (180.0, 195.0)), [0.3, 0.85, 0.4, 1.0]),
        ],
    )
}

fn triangle(a: (f64, f64), b: (f64, f64), c: (f64, f64)) -> BezPath {
    let mut p = BezPath::new();
    p.move_to(a);
    p.line_to(b);
    p.line_to(c);
    p.close_path();
    p
}

pub fn strokes_scene() -> DisplayList {
    let mut wave = BezPath::new();
    wave.move_to((20.0, 160.0));
    wave.curve_to((80.0, 60.0), (140.0, 220.0), (300.0, 120.0));
    let mut zigzag = BezPath::new();
    zigzag.move_to((20.0, 30.0));
    for i in 1..8 {
        zigzag.line_to((20.0 + i as f64 * 38.0, if i % 2 == 1 { 80.0 } else { 30.0 }));
    }
    display_list(
        320,
        200,
        vec![
            stroked(wave, [1.0, 1.0, 1.0, 1.0], 4.0, None, Cap::Round, Join::Round),
            stroked(zigzag.clone(), [0.95, 0.5, 0.2, 1.0], 6.0, None, Cap::Butt, Join::Miter),
            stroked(Rect::new(60.0, 100.0, 260.0, 190.0).to_path(0.1), [0.4, 0.8, 1.0, 1.0], 3.0, Some(vec![12.0, 6.0]), Cap::Butt, Join::Miter),
            stroked(Circle::new((160.0, 145.0), 30.0).to_path(0.1), [0.9, 0.9, 0.3, 1.0], 2.0, Some(vec![5.0]), Cap::Square, Join::Bevel),
        ],
    )
}

/// Glyph outlines from kinemo-text, scaled to pixels (y flipped) like the frame builder.
pub fn text_scene() -> DisplayList {
    let opts = kinemo_text::TextOptions { size: 0.6, ..Default::default() };
    let layout = kinemo_text::layout("Bubble sort: **O(n²)** `swap`", &opts);
    let pixels_per_unit = 60.0;
    let to_pixels = Affine::new([pixels_per_unit, 0.0, 0.0, -pixels_per_unit, 320.0, 60.0]);
    let items = layout
        .glyphs
        .iter()
        .map(|glyph| filled(to_pixels * glyph.path.clone(), [0.93, 0.93, 0.95, 1.0]))
        .collect();
    display_list(640, 120, items)
}

pub fn opacity_scene() -> DisplayList {
    let mut half_red = filled(Rect::new(20.0, 20.0, 200.0, 180.0).to_path(0.1), [1.0, 0.0, 0.0, 1.0]);
    half_red.opacity = 0.5;
    let mut translucent_blue = filled(Circle::new((200.0, 100.0), 80.0).to_path(0.1), [0.1, 0.3, 1.0, 0.6]);
    translucent_blue.opacity = 0.8;
    let mut faded_stroke = stroked(Rect::new(60.0, 60.0, 280.0, 150.0).to_path(0.1), [0.2, 1.0, 0.3, 1.0], 8.0, None, Cap::Butt, Join::Round);
    faded_stroke.opacity = 0.35;
    let mut both = filled(Circle::new((100.0, 140.0), 40.0).to_path(0.1), [1.0, 0.9, 0.1, 1.0]);
    both.stroke = Some(Stroke { color: [1.0, 1.0, 1.0, 1.0], width: 4.0, dash: None, cap: Cap::Butt, join: Join::Miter });
    both.opacity = 0.6;
    display_list(320, 200, vec![half_red, translucent_blue, faded_stroke, both])
}

pub fn transparent_background_scene() -> DisplayList {
    let mut dl = opacity_scene();
    dl.background = [0.0; 4];
    dl
}

pub fn clip_scene() -> DisplayList {
    let mut clipped_circle = filled(Circle::new((160.0, 100.0), 90.0).to_path(0.1), [0.6, 0.3, 0.9, 1.0]);
    clipped_circle.clip = Some(Rect::new(70.0, 40.0, 250.0, 130.0).to_path(0.1));
    let mut clipped_dashes = stroked(
        Rect::new(30.0, 30.0, 290.0, 170.0).to_path(0.1),
        [1.0, 1.0, 1.0, 1.0],
        6.0,
        Some(vec![10.0, 5.0]),
        Cap::Round,
        Join::Round,
    );
    clipped_dashes.clip = Some(Circle::new((160.0, 100.0), 110.0).to_path(0.1));
    clipped_dashes.opacity = 0.7;
    display_list(320, 200, vec![clipped_circle, clipped_dashes])
}

pub fn even_odd_scene() -> DisplayList {
    let mut ring = Circle::new((160.0, 100.0), 80.0).to_path(0.1);
    ring.extend(Circle::new((160.0, 100.0), 40.0).to_path(0.1));
    let mut item = filled(ring, [0.2, 0.9, 0.8, 1.0]);
    item.fill_rule_even_odd = true;
    display_list(320, 200, vec![item])
}

pub fn all_scenes() -> Vec<(&'static str, DisplayList)> {
    vec![
        ("shapes", shapes_scene()),
        ("strokes_with_dashes", strokes_scene()),
        ("text_glyphs", text_scene()),
        ("opacity", opacity_scene()),
        ("transparent_background", transparent_background_scene()),
        ("clips", clip_scene()),
        ("even_odd", even_odd_scene()),
    ]
}

/// Ground truth for anti-aliasing: the CPU reference rendered at `factor`× in each
/// direction and box-filtered down (premultiplied average, returned straight alpha).
pub fn supersampled_reference(dl: &DisplayList, factor: u32) -> kinemo_render::raster::Image {
    let scale = factor as f64;
    let mut big = dl.clone();
    big.width *= factor;
    big.height *= factor;
    for item in &mut big.items {
        item.path.apply_affine(Affine::scale(scale));
        if let Some(clip) = &mut item.clip {
            clip.apply_affine(Affine::scale(scale));
        }
        if let Some(stroke) = &mut item.stroke {
            stroke.width *= scale;
            if let Some(dash) = &mut stroke.dash {
                dash.iter_mut().for_each(|d| *d *= scale);
            }
        }
    }
    let big_image = kinemo_render::raster::rasterize(&big, true);
    let samples = (factor * factor) as u64;
    let mut rgba = vec![0u8; (dl.width * dl.height * 4) as usize];
    for y in 0..dl.height {
        for x in 0..dl.width {
            let mut sum = [0u64; 4];
            for sy in 0..factor {
                for sx in 0..factor {
                    let i = (((y * factor + sy) * big.width + x * factor + sx) * 4) as usize;
                    let alpha = big_image.rgba[i + 3] as u64;
                    for (c, total) in sum.iter_mut().take(3).enumerate() {
                        *total += big_image.rgba[i + c] as u64 * alpha;
                    }
                    sum[3] += alpha;
                }
            }
            let o = ((y * dl.width + x) * 4) as usize;
            for c in 0..3 {
                rgba[o + c] = (sum[c] + sum[3] / 2).checked_div(sum[3]).unwrap_or(0) as u8;
            }
            rgba[o + 3] = ((sum[3] + samples / 2) / samples) as u8;
        }
    }
    kinemo_render::raster::Image { width: dl.width, height: dl.height, rgba }
}
