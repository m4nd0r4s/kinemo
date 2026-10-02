//! Per-pixel comparison of a GPU frame against the CPU (tiny-skia) reference.
//!
//! Pixels are compared premultiplied: straight-alpha color is meaningless at alpha 0 and
//! wildly quantized at alpha 1-2, while premultiplied values are what composites.
//!
//! Why the tolerance is anti-aliasing aware: tiny-skia's coverage (4× vertical
//! supersampling) is itself off by up to ~80 levels from an 8×8 supersampled ground truth
//! on high-contrast curved or thin edges, while Vello's analytic area coverage is usually
//! closer to that truth. A plain "max channel diff ≤ 8" between the two is therefore
//! unattainable on any edge. Instead every candidate channel must lie within
//! `max_neighborhood_difference` of the range spanned by the reference's 3×3
//! neighborhood (an edge may shift its coverage, but no color may appear that the
//! reference does not have nearby), and only a small fraction of pixels — the edge
//! pixels — may differ by more than `differing_pixel_threshold` at all.

use kinemo_render::raster::Image;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PixelTolerance {
    /// Bound on how far a candidate channel may fall outside the reference's 3×3 range.
    pub max_neighborhood_difference: u8,
    /// A pixel "differs" when any channel differs from the reference by more than this.
    pub differing_pixel_threshold: u8,
    /// Bound on the fraction of differing pixels (anti-aliased edges).
    pub max_fraction_of_differing_pixels: f64,
}

/// Documented GPU (Vello) tolerance against the tiny-skia reference.
///
/// Measured on Apple M4 Pro (Metal): the test scenes and 1080p bubble sort frames stay at
/// ≤ 4 levels outside the 3×3 neighborhood with ≤ 2.5% edge pixels. Known exceedances,
/// both from the reference's coverage quantization rather than GPU error: glyphs below
/// ~20 px (draft 540p labels, dense 18 px text) reach 19–25 levels outside the
/// neighborhood, and frames dense in thin strokes exceed 3% edge pixels.
pub const GPU_TOLERANCE: PixelTolerance = PixelTolerance {
    max_neighborhood_difference: 8,
    differing_pixel_threshold: 2,
    max_fraction_of_differing_pixels: 0.03,
};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ImageDifference {
    /// Largest plain per-channel difference (reported, not bounded).
    pub max_channel_difference: u8,
    /// Largest distance of a candidate channel outside the reference 3×3 range.
    pub max_neighborhood_difference: u8,
    /// Pixels with any channel differing by more than the tolerance's threshold.
    pub differing_pixels: usize,
    pub total_pixels: usize,
    /// Mean absolute per-channel difference, in levels.
    pub mean_absolute_difference: f64,
}

impl ImageDifference {
    pub fn fraction_of_differing_pixels(&self) -> f64 {
        self.differing_pixels as f64 / self.total_pixels.max(1) as f64
    }

    pub fn is_within(&self, tolerance: &PixelTolerance) -> bool {
        self.max_neighborhood_difference <= tolerance.max_neighborhood_difference
            && self.fraction_of_differing_pixels() <= tolerance.max_fraction_of_differing_pixels
    }
}

fn premultiplied(image: &Image) -> Vec<[u8; 4]> {
    image
        .rgba
        .as_chunks::<4>()
        .0
        .iter()
        .map(|px| {
            let alpha = px[3] as u32;
            let premultiply = |c: u8| ((c as u32 * alpha + 127) / 255) as u8;
            [premultiply(px[0]), premultiply(px[1]), premultiply(px[2]), px[3]]
        })
        .collect()
}

/// Distance of `value` outside the channel's range over the 3×3 neighborhood of (x, y).
fn distance_outside_neighborhood(reference: &[[u8; 4]], width: usize, height: usize, x: usize, y: usize, channel: usize, value: u8) -> u8 {
    let (mut low, mut high) = (u8::MAX, u8::MIN);
    for ny in y.saturating_sub(1)..(y + 2).min(height) {
        for nx in x.saturating_sub(1)..(x + 2).min(width) {
            let v = reference[ny * width + nx][channel];
            low = low.min(v);
            high = high.max(v);
        }
    }
    if value < low { low - value } else { value.saturating_sub(high) }
}

/// Compares two same-sized images. Panics if the sizes differ.
pub fn image_difference(reference: &Image, candidate: &Image, tolerance: &PixelTolerance) -> ImageDifference {
    assert_eq!((reference.width, reference.height), (candidate.width, candidate.height), "image sizes differ");
    assert_eq!(reference.rgba.len(), candidate.rgba.len(), "pixel buffer sizes differ");
    let (width, height) = (reference.width as usize, reference.height as usize);
    let (reference, candidate) = (premultiplied(reference), premultiplied(candidate));
    let mut result = ImageDifference {
        max_channel_difference: 0,
        max_neighborhood_difference: 0,
        differing_pixels: 0,
        total_pixels: reference.len(),
        mean_absolute_difference: 0.0,
    };
    let mut absolute_sum = 0u64;
    for (index, (a, b)) in reference.iter().zip(&candidate).enumerate() {
        let pixel_max = (0..4).map(|c| a[c].abs_diff(b[c])).max().unwrap_or(0);
        absolute_sum += (0..4).map(|c| a[c].abs_diff(b[c]) as u64).sum::<u64>();
        result.max_channel_difference = result.max_channel_difference.max(pixel_max);
        if pixel_max > tolerance.differing_pixel_threshold {
            result.differing_pixels += 1;
            let (x, y) = (index % width, index / width);
            for (c, &value) in b.iter().enumerate() {
                let outside = distance_outside_neighborhood(&reference, width, height, x, y, c, value);
                result.max_neighborhood_difference = result.max_neighborhood_difference.max(outside);
            }
        }
    }
    result.mean_absolute_difference = absolute_sum as f64 / (reference.len().max(1) * 4) as f64;
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn image(width: u32, pixels: &[[u8; 4]]) -> Image {
        Image { width, height: pixels.len() as u32 / width, rgba: pixels.concat() }
    }

    #[test]
    fn edge_shifts_are_tolerated_but_new_colors_are_not() {
        let black = [0, 0, 0, 255];
        let white = [255, 255, 255, 255];
        let reference = image(4, &[black, black, white, white]);
        let shifted_edge = image(4, &[black, [128, 128, 128, 255], white, white]);
        let d = image_difference(&reference, &shifted_edge, &GPU_TOLERANCE);
        assert_eq!((d.max_channel_difference, d.max_neighborhood_difference, d.differing_pixels), (128, 0, 1));
        let wrong_color = image(4, &[[0, 0, 40, 255], black, white, white]);
        let d = image_difference(&reference, &wrong_color, &GPU_TOLERANCE);
        assert_eq!(d.max_neighborhood_difference, 40);
        assert!(!d.is_within(&GPU_TOLERANCE));
    }

    #[test]
    fn compares_premultiplied_so_transparent_color_is_ignored() {
        let reference = image(2, &[[0, 0, 0, 0], [10, 10, 10, 255]]);
        let candidate = image(2, &[[200, 9, 9, 1], [11, 10, 10, 255]]);
        let d = image_difference(&reference, &candidate, &GPU_TOLERANCE);
        assert!(d.max_channel_difference <= 1);
        assert_eq!(d.differing_pixels, 0);
    }
}
