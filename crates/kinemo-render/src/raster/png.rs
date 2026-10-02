use super::Image;

/// Encode a straight-alpha RGBA8 image as PNG bytes.
pub fn encode_png(img: &Image) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut enc = ::png::Encoder::new(&mut out, img.width, img.height);
        enc.set_color(::png::ColorType::Rgba);
        enc.set_depth(::png::BitDepth::Eight);
        let mut writer = enc.write_header().expect("png header");
        writer.write_image_data(&img.rgba).expect("png data: rgba length must be width*height*4");
    }
    out
}
