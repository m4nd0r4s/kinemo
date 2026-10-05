use super::*;
use kurbo::{Rect, Shape};

fn px(img: &Image, x: u32, y: u32) -> [u8; 4] {
    let i = ((y * img.width + x) * 4) as usize;
    img.rgba[i..i + 4].try_into().unwrap()
}

fn square_item(fill: Option<Fill>, stroke: Option<Stroke>) -> DrawItem {
    DrawItem {
        path: Rect::new(8.0, 8.0, 24.0, 24.0).to_path(0.1),
        fill,
        stroke,
        opacity: 1.0,
        clip: None,
        fill_rule_even_odd: false,
        image: None,
        dots: None,
    }
}

fn dl(items: Vec<DrawItem>) -> DisplayList {
    DisplayList { width: 32, height: 32, background: [0.0, 0.0, 0.0, 1.0], items }
}

#[test]
fn red_square_on_black() {
    let red = Fill { color: [1.0, 0.0, 0.0, 1.0] };
    let img = rasterize(&dl(vec![square_item(Some(red), None)]), true);
    assert_eq!(img.rgba.len(), 32 * 32 * 4);
    assert_eq!(px(&img, 16, 16), [255, 0, 0, 255]);
    assert_eq!(px(&img, 8, 8), [255, 0, 0, 255]);
    assert_eq!(px(&img, 2, 2), [0, 0, 0, 255]);
    assert_eq!(px(&img, 24, 24), [0, 0, 0, 255]);
}

#[test]
fn opacity_and_straight_alpha() {
    let mut item = square_item(Some(Fill { color: [1.0, 0.0, 0.0, 1.0] }), None);
    item.opacity = 0.5;
    let mut d = dl(vec![item]);
    d.background = [0.0; 4];
    let img = rasterize(&d, false);
    let p = px(&img, 16, 16);
    assert_eq!(p[0], 255); // un-premultiplied
    assert!((p[3] as i32 - 128).abs() <= 1);
    assert_eq!(px(&img, 1, 1), [0, 0, 0, 0]);
}

#[test]
fn clip_and_stroke() {
    let mut item = square_item(
        Some(Fill { color: [0.0, 1.0, 0.0, 1.0] }),
        Some(Stroke { color: [0.0, 0.0, 1.0, 1.0], width: 2.0, dash: Some(vec![2.0]), cap: Cap::Butt, join: Join::Miter }),
    );
    item.clip = Some(Rect::new(0.0, 0.0, 16.0, 32.0).to_path(0.1));
    let img = rasterize(&dl(vec![item]), false);
    assert_eq!(px(&img, 12, 16), [0, 255, 0, 255]);
    assert_eq!(px(&img, 20, 16), [0, 0, 0, 255]); // clipped
    assert_eq!(px(&img, 13, 8)[2], 255); // stroke over top edge (dash on)
    assert_eq!(px(&img, 15, 8)[2], 0); // dash gap
}

#[test]
fn deterministic_and_png() {
    let d = dl(vec![square_item(Some(Fill { color: [0.2, 0.4, 0.6, 0.7] }), None)]);
    let a = rasterize(&d, true);
    let b = rasterize(&d, true);
    assert_eq!(a.rgba, b.rgba);
    let bytes = encode_png(&a);
    assert_eq!(&bytes[..8], b"\x89PNG\r\n\x1a\n");
    let dec = ::png::Decoder::new(std::io::Cursor::new(bytes));
    let mut reader = dec.read_info().unwrap();
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).unwrap();
    assert_eq!((info.width, info.height), (32, 32));
    assert_eq!(&buf[..info.buffer_size()], &a.rgba[..]);
}

#[test]
fn cpu_backend_is_the_rasterizer_and_the_fallback() {
    let d = dl(vec![square_item(Some(Fill { color: [0.2, 0.4, 0.6, 0.7] }), None)]);
    let cpu = backend(BackendKind::Cpu);
    assert_eq!(cpu.name(), "cpu-tiny-skia");
    assert_eq!(cpu.rasterize(&d, true).rgba, rasterize(&d, true).rgba);
    let batch = cpu.rasterize_batch(&[d.clone(), d.clone()], true);
    assert_eq!(batch.len(), 2);
    // No GPU factory is installed in this crate's tests.
    assert_eq!(backend(BackendKind::GpuWithCpuFallback).name(), "cpu-tiny-skia");
}

fn checker_bitmap() -> std::sync::Arc<Bitmap> {
    // 2×2: red, green / blue, transparent (premultiplied).
    let premultiplied_rgba = vec![255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 0, 0, 0, 0];
    std::sync::Arc::new(Bitmap { width: 2, height: 2, premultiplied_rgba, average_color: [0.25, 0.25, 0.25, 0.75], encoded: vec![], mime: "image/png" })
}

fn image_item(transform: kurbo::Affine, outline: Rect, opacity: f64) -> DrawItem {
    DrawItem {
        path: outline.to_path(0.1),
        fill: None,
        stroke: None,
        opacity,
        clip: None,
        fill_rule_even_odd: false,
        image: Some(ImagePaint { bitmap: checker_bitmap(), transform }),
        dots: None,
    }
}

#[test]
fn image_is_scaled_into_its_outline() {
    // 2×2 image scaled ×8 at (8, 8): each source pixel covers an 8×8 block.
    let item = image_item(kurbo::Affine::new([8.0, 0.0, 0.0, 8.0, 8.0, 8.0]), Rect::new(8.0, 8.0, 24.0, 24.0), 1.0);
    let img = rasterize(&dl(vec![item]), true);
    assert_eq!(px(&img, 10, 10), [255, 0, 0, 255]);
    assert_eq!(px(&img, 21, 10), [0, 255, 0, 255]);
    assert_eq!(px(&img, 10, 21), [0, 0, 255, 255]);
    assert_eq!(px(&img, 21, 21), [0, 0, 0, 255]); // transparent texel over black
    assert_eq!(px(&img, 4, 4), [0, 0, 0, 255]); // outside the outline
    // Bilinear: the boundary between red and green blends both.
    let mid = px(&img, 16, 10);
    assert!(mid[0] > 40 && mid[1] > 40, "{mid:?}");
}

#[test]
fn image_opacity_rotation_and_determinism() {
    let rotate = kurbo::Affine::translate((16.0, 16.0)) * kurbo::Affine::rotate(std::f64::consts::FRAC_PI_2) * kurbo::Affine::translate((-8.0, -8.0));
    let outline = rotate * Rect::new(0.0, 0.0, 16.0, 16.0).to_path(0.1);
    let mut item = image_item(rotate * kurbo::Affine::scale(8.0), Rect::ZERO, 0.5);
    item.path = outline;
    let a = rasterize(&dl(vec![item.clone()]), true);
    let b = rasterize(&dl(vec![item]), true);
    assert_eq!(a.rgba, b.rgba);
    // A quarter turn moves the red texel (top-left) to the top-right.
    let p = px(&a, 21, 10);
    assert!((p[0] as i32 - 128).abs() <= 2 && p[1] == 0 && p[2] == 0, "{p:?}");
}

fn dots_item(color: [f64; 4], centers: Vec<[f32; 2]>, radius: f32) -> DrawItem {
    let radii = vec![radius; centers.len()];
    let mut path = kurbo::BezPath::new();
    for &[x, y] in &centers {
        path.extend(kurbo::Circle::new((x as f64, y as f64), radius as f64).path_elements(0.1));
    }
    DrawItem { path, fill: Some(Fill { color }), stroke: None, opacity: 1.0, clip: None, fill_rule_even_odd: false, image: None, dots: Some(DotCloud { centers, radii }) }
}

#[test]
fn dots_are_stamped_as_disks() {
    let img = rasterize(&dl(vec![dots_item([1.0, 1.0, 1.0, 1.0], vec![[16.0, 16.0]], 4.0)]), true);
    assert_eq!(px(&img, 16, 16), [255, 255, 255, 255]);
    assert_eq!(px(&img, 16, 26), [0, 0, 0, 255]);
    let edge = px(&img, 19, 16)[0];
    assert!(edge > 0, "the edge is antialiased, not empty");
}

#[test]
fn overlapping_dots_of_one_color_do_not_darken_each_other() {
    let half_red = [1.0, 0.0, 0.0, 0.5];
    let single = rasterize(&dl(vec![dots_item(half_red, vec![[16.0, 16.0]], 4.0)]), true);
    let double = rasterize(&dl(vec![dots_item(half_red, vec![[16.0, 16.0], [16.5, 16.0]], 4.0)]), true);
    assert_eq!(px(&single, 16, 16), px(&double, 16, 16));
}

#[test]
fn dots_match_the_path_fill_closely() {
    let color = [0.3, 0.6, 0.9, 1.0];
    let centers: Vec<[f32; 2]> = (0..6).map(|i| [5.0 + i as f32 * 4.3, 12.0 + (i % 2) as f32 * 7.0]).collect();
    let stamped = rasterize(&dl(vec![dots_item(color, centers.clone(), 1.6)]), true);
    let mut filled = dots_item(color, centers, 1.6);
    filled.dots = None;
    let filled = rasterize(&dl(vec![filled]), true);
    let total = |img: &Image| img.rgba.iter().map(|&v| v as u64).sum::<u64>();
    let (a, b) = (total(&stamped) as f64, total(&filled) as f64);
    assert!((a - b).abs() / b < 0.02, "stamped {a} vs filled {b}");
}
