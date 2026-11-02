//! Bundled fonts (DejaVu). System fonts are never used, for determinism.

use std::sync::OnceLock;

use crate::types::FontStyle;

#[cfg(not(feature = "subset-fonts"))]
static REGULAR_DATA: &[u8] = include_bytes!("../../../assets/fonts/DejaVuSans.ttf");
#[cfg(not(feature = "subset-fonts"))]
static BOLD_DATA: &[u8] = include_bytes!("../../../assets/fonts/DejaVuSans-Bold.ttf");
#[cfg(not(feature = "subset-fonts"))]
static ITALIC_DATA: &[u8] = include_bytes!("../../../assets/fonts/DejaVuSans-Oblique.ttf");
#[cfg(not(feature = "subset-fonts"))]
static MONO_DATA: &[u8] = include_bytes!("../../../assets/fonts/DejaVuSansMono.ttf");

// The same faces cut to Latin, Greek, punctuation, arrows and mathematical
// symbols, without hinting: a quarter of the size, for builds that ship to a
// browser. `scripts/subset-fonts.sh` regenerates them.
#[cfg(feature = "subset-fonts")]
static REGULAR_DATA: &[u8] = include_bytes!("../../../assets/fonts/subset/DejaVuSans.ttf");
#[cfg(feature = "subset-fonts")]
static BOLD_DATA: &[u8] = include_bytes!("../../../assets/fonts/subset/DejaVuSans-Bold.ttf");
#[cfg(feature = "subset-fonts")]
static ITALIC_DATA: &[u8] = include_bytes!("../../../assets/fonts/subset/DejaVuSans-Oblique.ttf");
#[cfg(feature = "subset-fonts")]
static MONO_DATA: &[u8] = include_bytes!("../../../assets/fonts/subset/DejaVuSansMono.ttf");

pub(crate) type Face = rustybuzz::Face<'static>;

pub(crate) struct Fonts {
    regular: Face,
    bold: Face,
    italic: Face,
    mono: Face,
}

impl Fonts {
    pub(crate) fn get(&self, style: FontStyle) -> &Face {
        match style {
            FontStyle::Regular => &self.regular,
            FontStyle::Bold => &self.bold,
            FontStyle::Italic => &self.italic,
            FontStyle::Mono => &self.mono,
            FontStyle::Inline => &self.regular,
        }
    }
}

/// The global, lazily parsed font set.
pub(crate) fn fonts() -> &'static Fonts {
    static FONTS: OnceLock<Fonts> = OnceLock::new();
    FONTS.get_or_init(|| {
        let load = |d: &'static [u8]| Face::from_slice(d, 0).expect("bundled font");
        Fonts {
            regular: load(REGULAR_DATA),
            bold: load(BOLD_DATA),
            italic: load(ITALIC_DATA),
            mono: load(MONO_DATA),
        }
    })
}

/// Scale factor from font units to scene units for `face` at `size`.
pub(crate) fn scale(face: &Face, size: f64) -> f64 {
    size / face.units_per_em() as f64
}

/// Line metrics (ascender, descender) in scene units, from the regular font.
/// The descender is negative.
pub(crate) fn line_metrics(size: f64) -> (f64, f64) {
    let reg = fonts().get(FontStyle::Regular);
    let s = scale(reg, size);
    (reg.ascender() as f64 * s, reg.descender() as f64 * s)
}
