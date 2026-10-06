//! Color space conversion (sRGB ↔ OKLab) and perceptual color mixing.
//!
//! Colors are `[r, g, b, a]` in straight-alpha sRGB with components in `0..=1`.
//! OKLab colors are `[L, a, b, alpha]`; alpha is carried through unchanged.

/// Converts straight-alpha sRGB to OKLab (alpha passes through).
pub fn srgb_to_oklab(c: [f64; 4]) -> [f64; 4] {
    let r = srgb_to_linear(c[0]);
    let g = srgb_to_linear(c[1]);
    let b = srgb_to_linear(c[2]);

    let l = 0.412_221_470_8 * r + 0.536_332_536_3 * g + 0.051_445_992_9 * b;
    let m = 0.211_903_498_2 * r + 0.680_699_545_1 * g + 0.107_396_956_6 * b;
    let s = 0.088_302_461_9 * r + 0.281_718_837_6 * g + 0.629_978_700_5 * b;

    let (l, m, s) = (l.cbrt(), m.cbrt(), s.cbrt());

    [
        0.210_454_255_3 * l + 0.793_617_785_0 * m - 0.004_072_046_8 * s,
        1.977_998_495_1 * l - 2.428_592_205_0 * m + 0.450_593_709_9 * s,
        0.025_904_037_1 * l + 0.782_771_766_2 * m - 0.808_675_766_0 * s,
        c[3],
    ]
}

/// Converts OKLab back to straight-alpha sRGB. Out-of-gamut results are not
/// clamped here; [`mix`] clamps its output.
pub fn oklab_to_srgb(c: [f64; 4]) -> [f64; 4] {
    let l = c[0] + 0.396_337_777_4 * c[1] + 0.215_803_757_3 * c[2];
    let m = c[0] - 0.105_561_345_8 * c[1] - 0.063_854_172_8 * c[2];
    let s = c[0] - 0.089_484_177_5 * c[1] - 1.291_485_548_0 * c[2];

    let (l, m, s) = (l * l * l, m * m * m, s * s * s);

    let r = 4.076_741_662_1 * l - 3.307_711_591_3 * m + 0.230_969_929_2 * s;
    let g = -1.268_438_004_6 * l + 2.609_757_401_1 * m - 0.341_319_396_5 * s;
    let b = -0.004_196_086_3 * l - 0.703_418_614_7 * m + 1.707_614_701_0 * s;

    [linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(b), c[3]]
}

/// Mixes two sRGB colors at `t` in OKLab (alpha mixes linearly).
/// The result is clamped to `0..=1`; `t = 0` and `t = 1` return the inputs exactly.
pub fn mix(a: [f64; 4], b: [f64; 4], t: f64) -> [f64; 4] {
    if t == 0.0 {
        return clamp(a);
    }
    if t == 1.0 {
        return clamp(b);
    }
    let la = srgb_to_oklab(a);
    let lb = srgb_to_oklab(b);
    let mut out = [0.0; 4];
    for i in 0..4 {
        out[i] = la[i] * (1.0 - t) + lb[i] * t;
    }
    clamp(oklab_to_srgb(out))
}

/// Tints `color` toward `tint` at `t` but moves its lightness only half as far: hue and
/// chroma follow the tint, while lighter and darker parts stay lighter and darker. Used when a
/// group is emphasized, so its details stay readable (alpha is `color`'s).
pub fn tint_keeping_lightness(color: [f64; 4], tint: [f64; 4], t: f64) -> [f64; 4] {
    if t == 0.0 {
        return clamp(color);
    }
    let (from, to) = (srgb_to_oklab(color), srgb_to_oklab(tint));
    let lightness = from[0] + (to[0] - from[0]) * t / 2.0;
    let out = [lightness, from[1] + (to[1] - from[1]) * t, from[2] + (to[2] - from[2]) * t, color[3]];
    clamp(oklab_to_srgb(out))
}

fn clamp(c: [f64; 4]) -> [f64; 4] {
    c.map(|v| if v.is_nan() { 0.0 } else { v.clamp(0.0, 1.0) })
}

fn srgb_to_linear(c: f64) -> f64 {
    if c <= 0.040_45 {
        c / 12.92
    } else {
        ((c + 0.055) / 1.055).powf(2.4)
    }
}

fn linear_to_srgb(c: f64) -> f64 {
    if c <= 0.003_130_8 {
        c * 12.92
    } else {
        1.055 * c.powf(1.0 / 2.4) - 0.055
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn group_tint_keeps_parts_apart() {
        let yellow = [1.0, 0.85, 0.2, 1.0];
        let (light, dark) = ([0.95, 0.95, 0.95, 1.0], [0.3, 0.6, 0.9, 1.0]);
        let (a, b) = (tint_keeping_lightness(light, yellow, 1.0), tint_keeping_lightness(dark, yellow, 1.0));
        // Fully mixed, both would be exactly the tint; here the lighter part stays lighter.
        assert!(srgb_to_oklab(a)[0] > srgb_to_oklab(b)[0] + 0.05);
        assert_eq!(tint_keeping_lightness(dark, yellow, 0.0), dark);
    }

    fn close(a: [f64; 4], b: [f64; 4], eps: f64) -> bool {
        a.iter().zip(b).all(|(x, y)| (x - y).abs() < eps)
    }

    #[test]
    fn white_and_black() {
        let w = srgb_to_oklab([1.0, 1.0, 1.0, 1.0]);
        assert!(close(w, [1.0, 0.0, 0.0, 1.0], 1e-4), "{w:?}");
        let k = srgb_to_oklab([0.0, 0.0, 0.0, 0.5]);
        assert!(close(k, [0.0, 0.0, 0.0, 0.5], 1e-9), "{k:?}");
    }

    #[test]
    fn roundtrip() {
        for c in [
            [1.0, 0.0, 0.0, 1.0],
            [0.2, 0.4, 0.6, 0.3],
            [0.9, 0.9, 0.1, 1.0],
            [0.01, 0.02, 0.03, 0.0],
        ] {
            let back = oklab_to_srgb(srgb_to_oklab(c));
            assert!(close(back, c, 1e-6), "{c:?} -> {back:?}");
        }
    }

    #[test]
    fn mix_endpoints_and_alpha() {
        let a = [1.0, 0.0, 0.0, 1.0];
        let b = [0.0, 0.0, 1.0, 0.0];
        assert_eq!(mix(a, b, 0.0), a);
        assert_eq!(mix(a, b, 1.0), b);
        assert!((mix(a, b, 0.25)[3] - 0.75).abs() < 1e-12);
    }

    #[test]
    fn mix_avoids_gray_midpoint() {
        // Red→blue in sRGB passes through dull purple; OKLab keeps it lighter.
        let m = mix([1.0, 0.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0], 0.5);
        let srgb_mid_l = srgb_to_oklab([0.5, 0.0, 0.5, 1.0])[0];
        assert!(srgb_to_oklab(m)[0] > srgb_mid_l);
        assert!(m.iter().all(|v| (0.0..=1.0).contains(v)));
    }

    #[test]
    fn mix_gray_is_gray() {
        let m = mix([0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0], 0.5);
        assert!((m[0] - m[1]).abs() < 1e-6 && (m[1] - m[2]).abs() < 1e-6);
    }
}
