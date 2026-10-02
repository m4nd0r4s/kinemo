//! Global, bounded layout cache keyed by (text, options).

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use kurbo::Rect;

use crate::types::{Align, TextLayout, TextOptions};

#[derive(Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    text: String,
    size: u64,
    width: Option<u64>,
    line_height: u64,
    align: Align,
    flags: u8,
}

impl CacheKey {
    fn new(text: &str, o: &TextOptions) -> Self {
        CacheKey {
            text: text.to_owned(),
            size: o.size.to_bits(),
            width: o.width.map(f64::to_bits),
            line_height: o.line_height.to_bits(),
            align: o.align,
            flags: (o.tabular_nums as u8) | ((o.markup as u8) << 1) | ((o.mono as u8) << 2),
        }
    }
}

/// The cache is cleared when it reaches this many entries.
const CACHE_LIMIT: usize = 4096;

type Cache = Mutex<HashMap<CacheKey, Arc<TextLayout>>>;

fn cache() -> &'static Cache {
    static CACHE: OnceLock<Cache> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Lay out `text`. The logical bbox is centered at (0,0). Results are cached.
pub fn layout(text: &str, opts: &TextOptions) -> Arc<TextLayout> {
    let key = CacheKey::new(text, opts);
    if let Some(l) = cache().lock().unwrap_or_else(|e| e.into_inner()).get(&key) {
        return l.clone();
    }
    // Computed outside the lock; a concurrent duplicate computation is harmless
    // because layout is deterministic.
    let l = Arc::new(crate::layout::compute(text, opts));
    let mut c = cache().lock().unwrap_or_else(|e| e.into_inner());
    if c.len() >= CACHE_LIMIT {
        c.clear();
    }
    c.entry(key).or_insert(l).clone()
}

/// Logical bounding box of the laid-out text (= `layout(..).bbox`).
pub fn measure(text: &str, opts: &TextOptions) -> Rect {
    layout(text, opts).bbox
}
