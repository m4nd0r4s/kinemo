//! Contact sheet: frames of a scene in a labelled grid (`kinemo snap --sheet`), drawn by the
//! renderer itself (no ffmpeg).

use std::sync::Arc;

use kurbo::{Affine, Rect, Shape};
use rayon::prelude::*;

use kinemo_ir::Scene;
use kinemo_text::TextOptions;

use crate::raster::{rasterize, Bitmap, DisplayList, DrawItem, Fill, Image, ImagePaint};
use crate::renderer::{render_frame, RenderOptions};

/// Width of one frame in the sheet, in pixels.
pub const CELL_WIDTH: u32 = 480;
const GAP: f64 = 16.0;
/// Height of the band under each frame that holds its label.
const LABEL_BAND: f64 = 30.0;
const LABEL_SIZE: f64 = 15.0;
const BACKGROUND: [f64; 4] = [0.07, 0.07, 0.08, 1.0];
const LABEL_COLOR: [f64; 4] = [0.85, 0.86, 0.88, 1.0];

/// One image with `frames` (instant, label) laid out in `columns` columns.
pub fn contact_sheet(scene: &Scene, frames: &[(f64, String)], columns: usize) -> Image {
    let columns = columns.clamp(1, frames.len().max(1));
    let rows = frames.len().div_ceil(columns);
    let cell_w = CELL_WIDTH;
    let cell_h = ((CELL_WIDTH as f64) * scene.config.height as f64 / scene.config.width.max(1) as f64).round() as u32;
    let opts = RenderOptions { width: cell_w, height: cell_h, fps: scene.config.fps, antialias: true, transparent: false };
    let shots: Vec<Image> = frames.par_iter().map(|(t, _)| render_frame(scene, *t, &opts)).collect();

    let width = GAP + columns as f64 * (cell_w as f64 + GAP);
    let height = GAP + rows as f64 * (cell_h as f64 + LABEL_BAND + GAP);
    let mut items = Vec::new();
    for (i, ((_, label), shot)) in frames.iter().zip(shots).enumerate() {
        let x = GAP + (i % columns) as f64 * (cell_w as f64 + GAP);
        let y = GAP + (i / columns) as f64 * (cell_h as f64 + LABEL_BAND + GAP);
        items.push(frame_item(shot, x, y));
        items.extend(label_items(label, x + cell_w as f64 / 2.0, y + cell_h as f64 + LABEL_BAND / 2.0));
    }
    rasterize(&DisplayList { width: width.round() as u32, height: height.round() as u32, background: BACKGROUND, items }, true)
}

fn frame_item(shot: Image, x: f64, y: f64) -> DrawItem {
    let (w, h) = (shot.width as f64, shot.height as f64);
    let bitmap = Bitmap {
        width: shot.width,
        height: shot.height,
        premultiplied_rgba: premultiplied(&shot.rgba),
        average_color: [0.0, 0.0, 0.0, 1.0],
        encoded: Vec::new(),
        mime: "image/png",
    };
    DrawItem {
        path: Rect::new(x, y, x + w, y + h).to_path(1e-3),
        fill: None,
        stroke: None,
        opacity: 1.0,
        clip: None,
        fill_rule_even_odd: false,
        image: Some(ImagePaint { bitmap: Arc::new(bitmap), transform: Affine::translate((x, y)) }),
        dots: None,
    }
}

/// The label's glyphs centered at (`cx`, `cy`) in pixels.
fn label_items(label: &str, cx: f64, cy: f64) -> Vec<DrawItem> {
    let layout = kinemo_text::layout(label, &TextOptions { size: LABEL_SIZE, ..TextOptions::default() });
    let to_px = Affine::translate((cx, cy)) * Affine::scale_non_uniform(1.0, -1.0);
    layout
        .glyphs
        .iter()
        .map(|g| DrawItem {
            path: to_px * g.path.clone(),
            fill: Some(Fill { color: LABEL_COLOR }),
            stroke: None,
            opacity: 1.0,
            clip: None,
            fill_rule_even_odd: false,
            image: None,
            dots: None,
        })
        .collect()
}

fn premultiplied(straight: &[u8]) -> Vec<u8> {
    let (pixels, _) = straight.as_chunks::<4>();
    pixels
        .iter()
        .flat_map(|p| {
            let a = p[3] as u32;
            [(p[0] as u32 * a / 255) as u8, (p[1] as u32 * a / 255) as u8, (p[2] as u32 * a / 255) as u8, p[3]]
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn premultiplies_by_alpha() {
        assert_eq!(premultiplied(&[255, 128, 0, 128, 10, 20, 30, 255]), vec![128, 64, 0, 128, 10, 20, 30, 255]);
    }
}
