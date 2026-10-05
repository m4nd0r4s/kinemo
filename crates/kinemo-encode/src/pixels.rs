//! RGBA → planar YUV 4:2:0 (BT.709, limited range), done by the caller's threads so ffmpeg
//! receives frames ready to encode: its own conversion is single-threaded (bit-exact swscale)
//! and RGBA is 2.7× more data through the pipe.
//!
//! Integer arithmetic only, so every machine produces the same bytes.

/// Fixed-point (×65536) BT.709 coefficients for 8-bit limited range: luma scaled by 219/255,
/// chroma by 224/255.
const Y_COEFFICIENTS: [i32; 3] = [11966, 40254, 4064];
const CB_COEFFICIENTS: [i32; 3] = [-6596, -22189, 28785];
const CR_COEFFICIENTS: [i32; 3] = [28784, -26145, -2639];

/// Even dimensions (4:2:0 needs them): one extra black column or row when odd, as ffmpeg's
/// `pad` did before.
pub fn even_size(width: u32, height: u32) -> (u32, u32) {
    (width + (width & 1), height + (height & 1))
}

/// Bytes of a YUV 4:2:0 frame of `width` × `height` (after rounding up to even).
pub fn yuv420_len(width: u32, height: u32) -> usize {
    let (w, h) = even_size(width, height);
    (w as usize * h as usize) * 3 / 2
}

fn dot(coefficients: [i32; 3], [r, g, b]: [i32; 3]) -> i32 {
    coefficients[0] * r + coefficients[1] * g + coefficients[2] * b
}

/// Converts a straight-alpha RGBA8 frame (alpha ignored) to YUV 4:2:0: the Y plane, then
/// Cb, then Cr. Chroma averages each 2×2 block; padding is black (Y 16, Cb = Cr = 128).
pub fn rgba_to_yuv420(rgba: &[u8], width: u32, height: u32) -> Vec<u8> {
    let (w, h) = (width as usize, height as usize);
    assert_eq!(rgba.len(), w * h * 4, "frame size does not match its dimensions");
    let (padded_w, padded_h) = even_size(width, height);
    let (padded_w, padded_h) = (padded_w as usize, padded_h as usize);
    let (chroma_w, chroma_h) = (padded_w / 2, padded_h / 2);
    let mut out = vec![0u8; padded_w * padded_h + 2 * chroma_w * chroma_h];
    let (luma, chroma) = out.split_at_mut(padded_w * padded_h);
    let (cb_plane, cr_plane) = chroma.split_at_mut(chroma_w * chroma_h);

    let pixel = |x: usize, y: usize| -> [i32; 3] {
        if x < w && y < h {
            let i = (y * w + x) * 4;
            [rgba[i] as i32, rgba[i + 1] as i32, rgba[i + 2] as i32]
        } else {
            [0, 0, 0]
        }
    };

    for y in 0..padded_h {
        let row = &mut luma[y * padded_w..(y + 1) * padded_w];
        for (x, value) in row.iter_mut().enumerate() {
            *value = (16 + ((dot(Y_COEFFICIENTS, pixel(x, y)) + (1 << 15)) >> 16)) as u8;
        }
    }
    for cy in 0..chroma_h {
        for cx in 0..chroma_w {
            let (x, y) = (cx * 2, cy * 2);
            let mut sum = [0i32; 3];
            for p in [pixel(x, y), pixel(x + 1, y), pixel(x, y + 1), pixel(x + 1, y + 1)] {
                sum = [sum[0] + p[0], sum[1] + p[1], sum[2] + p[2]];
            }
            // The 2×2 sum carries a factor 4: shift by 18 instead of 16.
            let index = cy * chroma_w + cx;
            cb_plane[index] = (128 + ((dot(CB_COEFFICIENTS, sum) + (1 << 17)) >> 18)).clamp(0, 255) as u8;
            cr_plane[index] = (128 + ((dot(CR_COEFFICIENTS, sum) + (1 << 17)) >> 18)).clamp(0, 255) as u8;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn solid(color: [u8; 3], width: u32, height: u32) -> Vec<u8> {
        (0..width * height).flat_map(|_| [color[0], color[1], color[2], 255]).collect()
    }

    #[test]
    fn primaries_land_on_bt709_limited_range() {
        // Reference values from the BT.709 matrix at 8-bit limited range.
        for (rgb, expected) in [([0, 0, 0], [16, 128, 128]), ([255, 255, 255], [235, 128, 128]), ([255, 0, 0], [63, 102, 240]), ([0, 255, 0], [173, 42, 26]), ([0, 0, 255], [32, 240, 118])] {
            let yuv = rgba_to_yuv420(&solid(rgb, 2, 2), 2, 2);
            assert_eq!([yuv[0], yuv[4], yuv[5]], expected, "{rgb:?}");
        }
    }

    #[test]
    fn odd_sizes_are_padded_with_black() {
        let yuv = rgba_to_yuv420(&solid([255, 255, 255], 3, 1), 3, 1);
        assert_eq!(yuv.len(), yuv420_len(3, 1));
        // Row 0: three white pixels then the black padding column; row 1 is all padding.
        assert_eq!(&yuv[..8], &[235, 235, 235, 16, 16, 16, 16, 16]);
    }
}
