//! Progressive reveal used by `draw` and `write`: trace the outline, then fill.

/// Fraction of the outline traced at draw progress `d`.
pub(super) fn outline_fraction(d: f64) -> f64 {
    (d / 0.7).clamp(0.0, 1.0)
}

/// Fill strength at draw progress `d`.
pub(super) fn fill_fraction(d: f64) -> f64 {
    ((d - 0.5) / 0.5).clamp(0.0, 1.0)
}

/// Draw progress of glyph `i` of `n` when the whole text is written up to `w`.
pub(super) fn glyph_progress(w: f64, i: usize, n: usize) -> f64 {
    if w >= 1.0 {
        return 1.0;
    }
    let window = (2.0 / (n as f64 + 1.0)).clamp(0.05, 1.0);
    let start = if n > 1 { i as f64 / (n - 1) as f64 * (1.0 - window) } else { 0.0 };
    ((w - start) / window).clamp(0.0, 1.0)
}

/// Draw progress of an arrow's part (0: the shaft, 1: the head): the shaft is traced
/// first and the head closes the drawing.
pub(super) fn arrow_part_progress(d: f64, index: usize) -> f64 {
    if d >= 1.0 {
        return 1.0;
    }
    match index {
        0 => (d / 0.75).clamp(0.0, 1.0),
        _ => ((d - 0.65) / 0.35).clamp(0.0, 1.0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_arrow_head_follows_its_shaft() {
        assert_eq!(arrow_part_progress(0.5, 1), 0.0);
        assert!(arrow_part_progress(0.5, 0) > 0.6);
        assert_eq!(arrow_part_progress(0.75, 0), 1.0);
        assert_eq!(arrow_part_progress(1.0, 1), 1.0);
    }

    #[test]
    fn glyphs_finish_in_order() {
        let n = 10;
        assert_eq!(glyph_progress(0.0, 0, n), 0.0);
        assert!(glyph_progress(0.5, 0, n) > glyph_progress(0.5, 9, n));
        assert_eq!(glyph_progress(1.0, 9, n), 1.0);
    }

    #[test]
    fn draw_phases_overlap() {
        assert_eq!(outline_fraction(0.7), 1.0);
        assert_eq!(fill_fraction(0.5), 0.0);
        assert_eq!(fill_fraction(1.0), 1.0);
    }
}
