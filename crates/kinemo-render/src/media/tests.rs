use super::*;

fn png_bytes(width: u32, height: u32, rgba: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut enc = ::png::Encoder::new(&mut out, width, height);
        enc.set_color(::png::ColorType::Rgba);
        enc.set_depth(::png::BitDepth::Eight);
        enc.write_header().unwrap().write_image_data(rgba).unwrap();
    }
    out
}

#[test]
fn decodes_png_premultiplied_with_mean_color() {
    let rgba = [255, 0, 0, 255, 0, 0, 255, 255, 0, 255, 0, 128, 255, 255, 255, 0];
    let bitmap = decode_bitmap(png_bytes(2, 2, &rgba)).unwrap();
    assert_eq!((bitmap.width, bitmap.height, bitmap.mime), (2, 2, "image/png"));
    assert_eq!(&bitmap.premultiplied_rgba[..4], &[255, 0, 0, 255]);
    assert_eq!(&bitmap.premultiplied_rgba[8..12], &[0, 128, 0, 128]);
    assert_eq!(&bitmap.premultiplied_rgba[12..], &[0, 0, 0, 0]);
    assert!((bitmap.average_color[3] - (255.0 + 255.0 + 128.0) / (4.0 * 255.0)).abs() < 1e-9);
}

#[test]
fn decodes_jpeg_and_rejects_other_formats() {
    let mut jpeg = Vec::new();
    let pixels = vec![200u8; 8 * 8 * 3];
    image::codecs::jpeg::JpegEncoder::new(&mut jpeg).encode(&pixels, 8, 8, image::ExtendedColorType::Rgb8).unwrap();
    let bitmap = decode_bitmap(jpeg).unwrap();
    assert_eq!((bitmap.width, bitmap.height, bitmap.mime), (8, 8, "image/jpeg"));
    assert!(bitmap.premultiplied_rgba.chunks(4).all(|p| p[3] == 255 && (p[0] as i32 - 200).abs() <= 2));
    assert!(decode_bitmap(b"not an image".to_vec()).is_err());
}

#[test]
fn load_bitmap_caches_by_file() {
    let dir = std::env::temp_dir().join(format!("kinemo-bitmap-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("one.png");
    std::fs::write(&path, png_bytes(1, 1, &[1, 2, 3, 255])).unwrap();
    let a = load_bitmap(&path).unwrap();
    let b = load_bitmap(&path).unwrap();
    assert!(std::sync::Arc::ptr_eq(&a, &b));
    assert!(load_bitmap(&dir.join("missing.png")).is_err());
    std::fs::remove_dir_all(&dir).unwrap();
}

const DRAWING: &str = r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">
  <g id="motor" opacity="0.5">
    <rect id="body" x="0" y="0" width="40" height="50" fill="#ff0000"/>
  </g>
  <path id="wire" d="M 40 25 L 100 25" fill="none" stroke="#0000ff" stroke-width="2"/>
  <path d="M 60 0 L 100 0 L 100 10 Z" fill="#00ff00" fill-opacity="0.25" fill-rule="evenodd"/>
</svg>"##;

/// `(d, fill, stroke, stroke_width, even_odd)` of a path node.
type PathParts<'a> = (&'a str, Option<[f64; 4]>, Option<[f64; 4]>, f64, bool);

fn path_parts(node: &SvgNode) -> PathParts<'_> {
    match &node.kind {
        SvgNodeKind::Path { d, fill, stroke, stroke_width, even_odd } => (d, *fill, *stroke, *stroke_width, *even_odd),
        SvgNodeKind::Group { .. } => panic!("expected a path"),
    }
}

#[test]
fn imports_groups_paths_ids_and_styles() {
    let svg = import_svg(DRAWING.as_bytes(), 3.0, 1080.0 / 8.0).unwrap();
    assert!((svg.height - 3.0).abs() < 1e-6 && (svg.width - 6.0).abs() < 1e-6);
    assert_eq!(svg.children.len(), 3);
    let motor = &svg.children[0];
    assert_eq!(motor.id.as_deref(), Some("motor"));
    let SvgNodeKind::Group { opacity, children } = &motor.kind else { panic!("motor is a group") };
    assert!((opacity - 0.5).abs() < 1e-6);
    assert_eq!(children[0].id.as_deref(), Some("body"));
    let (d, fill, stroke, _, _) = path_parts(&children[0]);
    assert_eq!(fill, Some([1.0, 0.0, 0.0, 1.0]));
    assert!(stroke.is_none());
    // Body spans x 0..40 of 100 (scene -3..-0.6) and the full height, y flipped.
    let body = kurbo::BezPath::from_svg(d).unwrap();
    let b = kurbo::Shape::bounding_box(&body);
    assert!((b.x0 + 3.0).abs() < 1e-4 && (b.x1 + 0.6).abs() < 1e-4 && (b.y0 + 1.5).abs() < 1e-4 && (b.y1 - 1.5).abs() < 1e-4);

    let (_, fill, stroke, width, _) = path_parts(&svg.children[1]);
    assert_eq!(svg.children[1].id.as_deref(), Some("wire"));
    assert!(fill.is_none());
    assert_eq!(stroke, Some([0.0, 0.0, 1.0, 1.0]));
    // 2 SVG units = 0.12 scene units = 0.12 * 135 stroke px.
    assert!((width - 0.12 * 135.0).abs() < 1e-3);

    let (d, fill, _, _, even_odd) = path_parts(&svg.children[2]);
    assert!(svg.children[2].id.is_none() && even_odd);
    assert!((fill.unwrap()[3] - 0.25).abs() < 1e-6);
    // The triangle sits at the top (SVG y = 0..10 → scene y = 1.5..0.9).
    let top = kurbo::Shape::bounding_box(&kurbo::BezPath::from_svg(d).unwrap());
    assert!((top.y1 - 1.5).abs() < 1e-4 && (top.y0 - 0.9).abs() < 1e-4);
}

#[test]
fn invalid_svg_is_an_error() {
    assert!(import_svg(b"<not-svg", 3.0, 135.0).is_err());
}
