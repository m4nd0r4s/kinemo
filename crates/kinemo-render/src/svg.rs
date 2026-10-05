//! SVG export of a single frame (`kinemo render --format svg --at t`): vector output for
//! documents, built from the same display list as the raster frame.

use std::fmt::Write;

use kinemo_ir::Scene;

use crate::frame::{display_list, FrameSize};
use crate::raster::{Cap, DisplayList, ImagePaint, Join};

fn rgba(c: [f64; 4]) -> (String, f64) {
    let to = |v: f64| (v.clamp(0.0, 1.0) * 255.0).round() as u8;
    (format!("#{:02x}{:02x}{:02x}", to(c[0]), to(c[1]), to(c[2])), c[3].clamp(0.0, 1.0))
}

fn cap(c: Cap) -> &'static str {
    match c {
        Cap::Butt => "butt",
        Cap::Round => "round",
        Cap::Square => "square",
    }
}

fn join(j: Join) -> &'static str {
    match j {
        Join::Miter => "miter",
        Join::Round => "round",
        Join::Bevel => "bevel",
    }
}

pub fn display_list_to_svg(dl: &DisplayList) -> String {
    let mut out = String::new();
    let _ = writeln!(
        out,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">"#,
        w = dl.width,
        h = dl.height
    );
    let (bg, bg_alpha) = rgba(dl.background);
    if bg_alpha > 0.0 {
        let _ = writeln!(out, r#"<rect width="100%" height="100%" fill="{bg}" fill-opacity="{bg_alpha:.4}"/>"#);
    }
    for (i, item) in dl.items.iter().enumerate() {
        let d = item.path.to_svg();
        if d.is_empty() {
            continue;
        }
        let mut attrs = String::new();
        match &item.fill {
            Some(f) => {
                let (c, a) = rgba(f.color);
                let _ = write!(attrs, r#" fill="{c}" fill-opacity="{a:.4}""#);
                if item.fill_rule_even_odd {
                    attrs.push_str(r#" fill-rule="evenodd""#);
                }
            }
            None => attrs.push_str(r#" fill="none""#),
        }
        if let Some(s) = &item.stroke {
            let (c, a) = rgba(s.color);
            let _ = write!(
                attrs,
                r#" stroke="{c}" stroke-opacity="{a:.4}" stroke-width="{:.3}" stroke-linecap="{}" stroke-linejoin="{}""#,
                s.width,
                cap(s.cap),
                join(s.join)
            );
            if let Some(dash) = &s.dash {
                let list: Vec<String> = dash.iter().map(|d| format!("{d:.2}")).collect();
                let _ = write!(attrs, r#" stroke-dasharray="{}""#, list.join(" "));
            }
        }
        if item.opacity < 1.0 {
            let _ = write!(attrs, r#" opacity="{:.4}""#, item.opacity);
        }
        if let Some(clip) = &item.clip {
            let _ = writeln!(out, r#"<clipPath id="c{i}"><path d="{}"/></clipPath>"#, clip.to_svg());
            let _ = write!(attrs, r#" clip-path="url(#c{i})""#);
        }
        let painted = item.fill.is_some() || item.stroke.is_some();
        if painted || item.image.is_none() {
            let _ = writeln!(out, r#"<path d="{d}"{attrs}/>"#);
        }
        if let Some(image) = &item.image {
            write_image(&mut out, image, item.opacity, item.clip.is_some().then_some(i));
        }
    }
    out.push_str("</svg>\n");
    out
}

/// An `<image>` with the original file embedded as a base64 data URI.
fn write_image(out: &mut String, image: &ImagePaint, opacity: f64, clip: Option<usize>) {
    use base64::Engine as _;
    let bitmap = &image.bitmap;
    let data = base64::engine::general_purpose::STANDARD.encode(&bitmap.encoded);
    let [a, b, c, d, e, f] = image.transform.as_coeffs();
    let mut attrs = String::new();
    if opacity < 1.0 {
        let _ = write!(attrs, r#" opacity="{opacity:.4}""#);
    }
    if let Some(i) = clip {
        let _ = write!(attrs, r#" clip-path="url(#c{i})""#);
    }
    let _ = writeln!(
        out,
        r#"<image width="{}" height="{}" preserveAspectRatio="none" transform="matrix({a:.6} {b:.6} {c:.6} {d:.6} {e:.4} {f:.4})" href="data:{};base64,{data}"{attrs}/>"#,
        bitmap.width, bitmap.height, bitmap.mime
    );
}

/// SVG document of the frame at `t`, at the scene's own resolution.
pub fn render_svg(scene: &Scene, t: f64, transparent: bool) -> String {
    let size = FrameSize { width: scene.config.width, height: scene.config.height };
    display_list_to_svg(&display_list(scene, t, size, transparent))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::raster::{DrawItem, Fill};
    use kurbo::{Rect, Shape};

    #[test]
    fn writes_paths_with_fill() {
        let dl = DisplayList {
            width: 10,
            height: 10,
            background: [0.0, 0.0, 0.0, 1.0],
            items: vec![DrawItem {
                path: Rect::new(1.0, 1.0, 5.0, 5.0).to_path(0.1),
                fill: Some(Fill { color: [1.0, 0.0, 0.0, 1.0] }),
                stroke: None,
                opacity: 1.0,
                clip: None,
                fill_rule_even_odd: false,
                image: None,
                dots: None,
            }],
        };
        let svg = display_list_to_svg(&dl);
        assert!(svg.contains(r##"fill="#ff0000""##) && svg.contains("<path d=\"M"));
    }
}
