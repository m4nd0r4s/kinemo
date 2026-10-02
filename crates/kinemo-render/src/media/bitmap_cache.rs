//! Decoding of PNG/JPEG files into [`Bitmap`]s, once per file.
//!
//! The cache key includes the file's size and modification time, so editing an image
//! while the preview server runs picks up the new pixels; decoding itself is
//! deterministic (same bytes → same pixels).

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::SystemTime;

use crate::raster::Bitmap;

type CacheKey = (PathBuf, u64, Option<SystemTime>);

fn cache() -> &'static Mutex<HashMap<CacheKey, Arc<Bitmap>>> {
    static CACHE: OnceLock<Mutex<HashMap<CacheKey, Arc<Bitmap>>>> = OnceLock::new();
    CACHE.get_or_init(Mutex::default)
}

/// The decoded image at `path`, from the cache when the file did not change.
pub fn load_bitmap(path: &Path) -> Result<Arc<Bitmap>, String> {
    let meta = std::fs::metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let key = (path.to_path_buf(), meta.len(), meta.modified().ok());
    if let Some(hit) = cache().lock().map_err(|e| e.to_string())?.get(&key) {
        return Ok(hit.clone());
    }
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let bitmap = Arc::new(decode_bitmap(bytes).map_err(|e| format!("{}: {e}", path.display()))?);
    let mut map = cache().lock().map_err(|e| e.to_string())?;
    // Older versions of the same file are dropped.
    map.retain(|(p, _, _), _| p != path);
    map.insert(key, bitmap.clone());
    Ok(bitmap)
}

/// Decodes PNG or JPEG bytes.
pub fn decode_bitmap(encoded: Vec<u8>) -> Result<Bitmap, String> {
    let format = image::guess_format(&encoded).map_err(|e| e.to_string())?;
    let mime = match format {
        image::ImageFormat::Png => "image/png",
        image::ImageFormat::Jpeg => "image/jpeg",
        other => return Err(format!("unsupported image format: {other:?} (use PNG or JPEG)")),
    };
    let rgba = image::load_from_memory_with_format(&encoded, format).map_err(|e| e.to_string())?.to_rgba8();
    let (width, height) = rgba.dimensions();
    if width == 0 || height == 0 {
        return Err("empty image".into());
    }
    let mut premultiplied = rgba.into_raw();
    let mut sums = [0u64; 4];
    for px in premultiplied.as_chunks_mut::<4>().0 {
        let a = px[3] as u32;
        for (sum, &channel) in sums.iter_mut().zip(px.iter()) {
            *sum += channel as u64;
        }
        for c in &mut px[..3] {
            *c = ((*c as u32 * a + 127) / 255) as u8;
        }
    }
    let n = (width as u64 * height as u64 * 255) as f64;
    let average_color = sums.map(|s| s as f64 / n);
    Ok(Bitmap { width, height, premultiplied_rgba: premultiplied, average_color, encoded, mime })
}
