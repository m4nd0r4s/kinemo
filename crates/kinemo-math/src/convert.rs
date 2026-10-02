//! LaTeX → typst: mitex conversion of the marked LaTeX, and assembly of the
//! typst document (page setup, prelude, marker functions, equation).

use crate::error::MathError;
use crate::typst_rename::rename_identifiers;

/// Font size of the typst document, in pt. Layout is scaled to scene units
/// afterwards, so the value only matters for rounding.
pub(crate) const DOCUMENT_FONT_PT: f64 = 10.0;

const PRELUDE: &str = include_str!("mitex_prelude.typ");

/// Maximum number of part-tree nodes that can carry a marker (24-bit colors).
/// Formulas with more nodes are laid out without markers.
pub(crate) const MAX_MARKERS: usize = (1 << 24) - 1;

/// Convert math-mode LaTeX to typst math markup with mitex.
pub(crate) fn latex_to_typst(latex: &str) -> Result<String, MathError> {
    let math = mitex::convert_math(latex, None).map_err(|message| classify_mitex_error(&message))?;
    Ok(rename_identifiers(&math))
}

fn classify_mitex_error(message: &str) -> MathError {
    let message = message.trim_start_matches("error: ");
    if let Some(command) = message.strip_prefix("unknown command: ") {
        return MathError::Unsupported { command: command.trim().to_owned() };
    }
    if let Some(env) = message.strip_prefix("unknown environment: ") {
        return MathError::Unsupported { command: format!("\\begin{{{}}}", env.trim()) };
    }
    MathError::Syntax(message.to_owned())
}

/// Color that marks part-tree node `id`: its 24-bit index as RGB (computed
/// the same way by `colortext` in the prelude).
#[cfg(test)]
pub(crate) fn marker_rgb(id: usize) -> [u8; 3] {
    [(id >> 16) as u8, (id >> 8) as u8, id as u8]
}

/// Part-tree node marked by color `rgb` (0 = root, also for unmarked black ink).
pub(crate) fn node_of_rgb(rgb: [u8; 3]) -> usize {
    ((rgb[0] as usize) << 16) | ((rgb[1] as usize) << 8) | rgb[2] as usize
}

/// The full typst document for one formula.
pub(crate) fn typst_document(math: &str, display: bool) -> String {
    let mut doc = String::with_capacity(PRELUDE.len() + math.len() + 256);
    doc.push_str("#set page(width: auto, height: auto, margin: 0pt, fill: none)\n");
    doc.push_str(&format!(
        "#set text(size: {DOCUMENT_FONT_PT}pt, font: \"New Computer Modern\", fill: black)\n"
    ));
    doc.push_str("#set par(justify: false)\n");
    doc.push_str(PRELUDE);
    if display {
        doc.push_str(&format!("$ {math} $\n"));
    } else {
        // The page is the paragraph's line: make it span the font's full height.
        doc.push_str("#set text(top-edge: \"ascender\", bottom-edge: \"descender\")\n");
        doc.push_str(&format!("${math}$\n"));
    }
    doc
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn marker_colors_round_trip() {
        for id in [0, 1, 255, 256, 4095, 70000] {
            assert_eq!(node_of_rgb(marker_rgb(id)), id);
        }
    }

    #[test]
    fn unknown_commands_are_unsupported() {
        assert!(matches!(classify_mitex_error("error: unknown command: \\foo"), MathError::Unsupported { command } if command == "\\foo"));
    }
}
